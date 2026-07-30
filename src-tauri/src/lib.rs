use std::ffi::OsString;
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::{Manager, State};
use tauri_plugin_dialog::DialogExt;

#[derive(Debug, PartialEq, Eq)]
pub struct ProcessSpec {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
}

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct AgentEndpoint {
    pid: u32,
    port: u16,
    base_url: String,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum ProcessRole {
    Agent,
    Comfyui,
}

trait AgentChild {
    fn id(&self) -> u32;
    fn try_exit(&mut self) -> Result<Option<String>, String>;
    fn terminate(&mut self);
}

impl AgentChild for Child {
    fn id(&self) -> u32 {
        Child::id(self)
    }

    fn try_exit(&mut self) -> Result<Option<String>, String> {
        self.try_wait()
            .map(|status| status.map(|status| status.to_string()))
            .map_err(|error| error.to_string())
    }

    fn terminate(&mut self) {
        let _ = self.kill();
        let _ = self.wait();
    }
}

struct ManagedProcess<C = Child> {
    role: ProcessRole,
    child: C,
    agent_port: Option<u16>,
}

struct ManagedProcesses(Mutex<Vec<ManagedProcess>>);

fn comfyui_entry_point(root: &Path) -> Option<PathBuf> {
    [root.join("main.py"), root.join("ComfyUI").join("main.py")]
        .into_iter()
        .find(|candidate| candidate.is_file())
}

pub fn validate_comfyui_directory_path(root: &Path) -> Result<(), String> {
    if !root.is_dir() {
        return Err("所选路径不是目录".into());
    }
    comfyui_entry_point(root)
        .map(|_| ())
        .ok_or_else(|| "目录中未找到 ComfyUI 的 main.py".into())
}

pub fn comfyui_process_spec(root: &Path) -> Result<ProcessSpec, String> {
    validate_comfyui_directory_path(root)?;
    let entry = comfyui_entry_point(root).expect("validated ComfyUI entry point");
    let current_dir = entry
        .parent()
        .expect("ComfyUI entry point has a parent")
        .to_path_buf();
    let mut python_candidates = vec![
        root.join("python_embeded").join("python.exe"),
        current_dir
            .parent()
            .unwrap_or(&current_dir)
            .join("python_embeded")
            .join("python.exe"),
    ];
    for base in [&current_dir, root] {
        python_candidates.push(base.join(".venv").join("Scripts").join("python.exe"));
        python_candidates.push(base.join("venv").join("Scripts").join("python.exe"));
    }
    let program = python_candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .unwrap_or_else(|| PathBuf::from("python"));

    Ok(ProcessSpec {
        program,
        current_dir,
        args: ["main.py", "--listen", "127.0.0.1", "--port", "8188"]
            .into_iter()
            .map(OsString::from)
            .collect(),
    })
}

pub fn select_agent_port<F>(mut is_available: F) -> Result<u16, String>
where
    F: FnMut(u16) -> bool,
{
    (8000..=8099)
        .find(|port| is_available(*port))
        .ok_or_else(|| "Agent 端口 8000 到 8099 均不可用".to_string())
}

pub fn debug_agent_process_spec(port: u16) -> ProcessSpec {
    let backend = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../backend");
    let virtualenv_python = backend.join(".venv").join("Scripts").join("python.exe");
    ProcessSpec {
        program: if virtualenv_python.is_file() {
            virtualenv_python
        } else {
            PathBuf::from("python")
        },
        current_dir: backend,
        args: [
            OsString::from("-m"),
            OsString::from("uvicorn"),
            OsString::from("app.main:app"),
            OsString::from("--host"),
            OsString::from("127.0.0.1"),
            OsString::from("--port"),
            OsString::from(port.to_string()),
        ]
        .into_iter()
        .collect(),
    }
}

pub fn packaged_agent_process_spec(backend_dir: &Path, port: u16) -> Result<ProcessSpec, String> {
    let executable = backend_dir.join("ai-art-agent-backend.exe");
    if !executable.is_file() {
        return Err(format!("未找到本地 Agent：{}", executable.display()));
    }
    Ok(ProcessSpec {
        program: executable,
        current_dir: backend_dir.to_path_buf(),
        args: [OsString::from("--port"), OsString::from(port.to_string())]
            .into_iter()
            .collect(),
    })
}

fn local_agent_process_spec(app: &tauri::AppHandle, port: u16) -> Result<ProcessSpec, String> {
    if cfg!(debug_assertions) {
        return Ok(debug_agent_process_spec(port));
    }

    let backend_dir = app
        .path()
        .resource_dir()
        .map_err(|error| error.to_string())?
        .join("backend");
    let executable = backend_dir.join("ai-art-agent-backend.exe");
    if !executable.is_file() {
        return Err(format!("未找到本地 Agent：{}", executable.display()));
    }
    Ok(ProcessSpec {
        program: executable,
        current_dir: backend_dir,
        args: [OsString::from("--port"), OsString::from(port.to_string())]
            .into_iter()
            .collect(),
    })
}

fn spawn_process(spec: &ProcessSpec) -> Result<Child, String> {
    let mut command = Command::new(&spec.program);
    command.args(&spec.args).current_dir(&spec.current_dir);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command.spawn().map_err(|error| {
        format!(
            "无法启动 {}：{error}",
            spec.program.as_os_str().to_string_lossy()
        )
    })
}

fn spawn_managed(
    spec: ProcessSpec,
    role: ProcessRole,
    reuse_existing: bool,
    processes: &ManagedProcesses,
) -> Result<u32, String> {
    let mut children = processes
        .0
        .lock()
        .map_err(|_| "进程状态锁已损坏".to_string())?;
    let mut index = 0;
    while index < children.len() {
        if children[index].role != role {
            index += 1;
            continue;
        }
        match children[index].child.try_wait() {
            Ok(None) if reuse_existing => return Ok(children[index].child.id()),
            Ok(None) => return Err("ComfyUI 已由应用启动，请先关闭后再切换目录".into()),
            Ok(Some(_)) => {
                children.remove(index);
            }
            Err(error) => return Err(format!("无法检查托管进程状态：{error}")),
        }
    }

    let mut command = Command::new(&spec.program);
    command.args(&spec.args).current_dir(&spec.current_dir);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let child = command.spawn().map_err(|error| {
        format!(
            "无法启动 {}：{error}",
            spec.program.as_os_str().to_string_lossy()
        )
    })?;
    let process_id = child.id();
    children.push(ManagedProcess {
        role,
        child,
        agent_port: None,
    });
    Ok(process_id)
}

#[cfg(windows)]
fn terminate_process_tree(child: &mut Child) {
    use std::os::windows::process::CommandExt;

    let process_id = child.id().to_string();
    let mut taskkill = Command::new("taskkill");
    taskkill
        .args(["/PID", process_id.as_str(), "/T", "/F"])
        .creation_flags(0x08000000);
    let _ = taskkill.status();
    let _ = child.wait();
}

#[cfg(not(windows))]
fn terminate_process_tree(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

fn stop_all(processes: &ManagedProcesses) -> Result<(), String> {
    let mut children = processes
        .0
        .lock()
        .map_err(|_| "进程状态锁已损坏".to_string())?;
    for mut process in children.drain(..) {
        terminate_process_tree(&mut process.child);
    }
    Ok(())
}

fn agent_endpoint(pid: u32, port: u16) -> AgentEndpoint {
    AgentEndpoint {
        pid,
        port,
        base_url: format!("http://127.0.0.1:{port}"),
    }
}

fn agent_port_is_available(port: u16) -> bool {
    TcpListener::bind(("127.0.0.1", port)).is_ok()
}

fn start_local_agent_core<C, A, S, W>(
    children: &mut Vec<ManagedProcess<C>>,
    mut is_available: A,
    mut spawn: S,
    mut wait_for_startup: W,
) -> Result<AgentEndpoint, String>
where
    C: AgentChild,
    A: FnMut(u16) -> bool,
    S: FnMut(u16) -> Result<C, String>,
    W: FnMut(),
{
    let mut index = 0;
    while index < children.len() {
        if children[index].role != ProcessRole::Agent {
            index += 1;
            continue;
        }
        match children[index].child.try_exit() {
            Ok(None) => {
                let port = children[index]
                    .agent_port
                    .ok_or_else(|| "托管 Agent 缺少运行时端口".to_string())?;
                return Ok(agent_endpoint(children[index].child.id(), port));
            }
            Ok(Some(_)) => {
                children.remove(index);
            }
            Err(error) => return Err(format!("无法检查托管 Agent 进程状态：{error}")),
        }
    }

    let mut minimum_port = 8000;
    loop {
        let port =
            select_agent_port(|candidate| candidate >= minimum_port && is_available(candidate))?;
        let mut child = spawn(port)?;
        wait_for_startup();
        match child.try_exit() {
            Ok(None) => {
                let endpoint = agent_endpoint(child.id(), port);
                children.push(ManagedProcess {
                    role: ProcessRole::Agent,
                    child,
                    agent_port: Some(port),
                });
                return Ok(endpoint);
            }
            Ok(Some(_)) if port < 8099 => {
                minimum_port = port + 1;
            }
            Ok(Some(status)) => {
                return Err(format!(
                    "Agent 无法绑定 8000 到 8099 端口（最后退出状态：{status}）"
                ));
            }
            Err(error) => {
                child.terminate();
                return Err(format!("无法检查新启动的 Agent 进程状态：{error}"));
            }
        }
    }
}

fn spawn_local_agent(
    app: &tauri::AppHandle,
    processes: &ManagedProcesses,
) -> Result<AgentEndpoint, String> {
    let mut children = processes
        .0
        .lock()
        .map_err(|_| "进程状态锁已损坏".to_string())?;
    start_local_agent_core(
        &mut children,
        agent_port_is_available,
        |port| {
            let spec = local_agent_process_spec(app, port)?;
            spawn_process(&spec)
        },
        || thread::sleep(Duration::from_millis(150)),
    )
}

#[tauri::command]
async fn select_comfyui_directory(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let Some(selection) = app.dialog().file().blocking_pick_folder() else {
        return Ok(None);
    };
    let path = selection.into_path().map_err(|error| error.to_string())?;
    validate_comfyui_directory_path(&path)?;
    Ok(Some(path.to_string_lossy().into_owned()))
}

#[tauri::command]
fn validate_comfyui_directory(path: String) -> Result<(), String> {
    validate_comfyui_directory_path(Path::new(&path))
}

#[tauri::command]
fn start_local_agent(
    app: tauri::AppHandle,
    processes: State<'_, ManagedProcesses>,
) -> Result<AgentEndpoint, String> {
    spawn_local_agent(&app, &processes)
}

#[tauri::command]
fn start_comfyui(path: String, processes: State<'_, ManagedProcesses>) -> Result<u32, String> {
    spawn_managed(
        comfyui_process_spec(Path::new(&path))?,
        ProcessRole::Comfyui,
        false,
        &processes,
    )
}

#[tauri::command]
fn stop_managed_processes(processes: State<'_, ManagedProcesses>) -> Result<(), String> {
    stop_all(&processes)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .manage(ManagedProcesses(Mutex::new(Vec::new())))
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            select_comfyui_directory,
            validate_comfyui_directory,
            start_local_agent,
            start_comfyui,
            stop_managed_processes
        ])
        .build(tauri::generate_context!())
        .expect("error while building AI Art Agent");

    app.run(|app_handle, event| {
        if matches!(event, tauri::RunEvent::Exit) {
            let processes = app_handle.state::<ManagedProcesses>();
            let _ = stop_all(&processes);
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FakeAgentChild {
        pid: u32,
        exit_status: Option<String>,
    }

    impl FakeAgentChild {
        fn running(pid: u32) -> Self {
            Self {
                pid,
                exit_status: None,
            }
        }

        fn exited(pid: u32) -> Self {
            Self {
                pid,
                exit_status: Some("exit code 1".to_string()),
            }
        }
    }

    impl AgentChild for FakeAgentChild {
        fn id(&self) -> u32 {
            self.pid
        }

        fn try_exit(&mut self) -> Result<Option<String>, String> {
            Ok(self.exit_status.clone())
        }

        fn terminate(&mut self) {}
    }

    #[test]
    fn reuses_the_saved_port_of_a_live_managed_agent() {
        let mut children = vec![ManagedProcess {
            role: ProcessRole::Agent,
            child: FakeAgentChild::running(52),
            agent_port: Some(8007),
        }];

        let endpoint = start_local_agent_core(
            &mut children,
            |_| panic!("a live managed Agent must not select a new port"),
            |_| -> Result<FakeAgentChild, String> {
                panic!("a live managed Agent must not spawn a new child")
            },
            || panic!("a live managed Agent must not wait for startup"),
        )
        .expect("reuse managed Agent");

        assert_eq!(endpoint.pid, 52);
        assert_eq!(endpoint.port, 8007);
        assert_eq!(endpoint.base_url, "http://127.0.0.1:8007");
        assert_eq!(children.len(), 1);
    }

    #[test]
    fn retries_the_next_port_when_a_new_agent_exits_early() {
        let mut children = Vec::new();
        let mut attempted_ports = Vec::new();

        let endpoint = start_local_agent_core(
            &mut children,
            |port| matches!(port, 8000 | 8001),
            |port| {
                attempted_ports.push(port);
                Ok(if port == 8000 {
                    FakeAgentChild::exited(60)
                } else {
                    FakeAgentChild::running(61)
                })
            },
            || {},
        )
        .expect("retry after early exit");

        assert_eq!(attempted_ports, vec![8000, 8001]);
        assert_eq!(endpoint.pid, 61);
        assert_eq!(endpoint.port, 8001);
        assert_eq!(endpoint.base_url, "http://127.0.0.1:8001");
        assert_eq!(children.len(), 1);
        assert_eq!(children[0].agent_port, Some(8001));
    }
}
