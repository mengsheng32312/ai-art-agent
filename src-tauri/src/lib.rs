use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::{Manager, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

const COMFYUI_MANAGER_LOADING_SCRIPT: &str =
    include_str!("../../frontend/src/lib/comfyuiManagerLoading.js");

#[derive(Debug, PartialEq, Eq)]
pub struct ProcessSpec {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
}

#[derive(Debug, PartialEq, Eq)]
pub enum ComfyuiStartDecision {
    Spawn,
    Reuse,
    Restart,
}

pub fn comfyui_start_decision(
    running_root: Option<&Path>,
    requested_root: &Path,
) -> ComfyuiStartDecision {
    match running_root {
        None => ComfyuiStartDecision::Spawn,
        Some(root) if root == requested_root => ComfyuiStartDecision::Reuse,
        Some(_) => ComfyuiStartDecision::Restart,
    }
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
    fn terminate(&mut self, timeout: Duration) -> Result<(), String>;
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

    fn terminate(&mut self, timeout: Duration) -> Result<(), String> {
        terminate_process_tree(self, timeout)
    }
}

struct ManagedProcess<C = Child> {
    role: ProcessRole,
    child: C,
    root: Option<PathBuf>,
    agent_port: Option<u16>,
}

struct ManagedProcesses(Mutex<Vec<ManagedProcess>>);

fn comfyui_entry_point(root: &Path) -> Option<PathBuf> {
    [root.join("main.py"), root.join("ComfyUI").join("main.py")]
        .into_iter()
        .find(|candidate| candidate.is_file())
}

fn comfyui_launcher_batch(root: &Path) -> Option<PathBuf> {
    [
        root.join("run_nvidia_gpu.bat"),
        root.join("run_cpu.bat"),
        root.join("run_nvidia_gpu_fast_fp16_accumulation.bat"),
        root.join("run_directml.bat"),
    ]
    .into_iter()
    .find(|candidate| candidate.is_file())
}

pub fn validate_comfyui_directory_path(root: &Path) -> Result<(), String> {
    if !root.is_dir() {
        return Err("所选路径不是目录".into());
    }
    comfyui_entry_point(root)
        .or_else(|| comfyui_launcher_batch(root))
        .map(|_| ())
        .ok_or_else(|| "目录中未找到 ComfyUI 的 main.py 或 portable 启动 .bat".into())
}

pub fn validate_comfyui_web_url(raw: &str) -> Result<tauri::Url, String> {
    let url = raw
        .trim()
        .parse::<tauri::Url>()
        .map_err(|_| "ComfyUI 地址无效".to_string())?;
    if !matches!(url.scheme(), "http" | "https") {
        return Err("ComfyUI 地址只支持 http 或 https".into());
    }
    Ok(url)
}

fn comfyui_python(root: &Path, current_dir: &Path) -> PathBuf {
    let mut candidates = vec![
        root.join("python_embeded").join("python.exe"),
        current_dir
            .parent()
            .unwrap_or(current_dir)
            .join("python_embeded")
            .join("python.exe"),
    ];
    for base in [current_dir, root] {
        candidates.push(base.join(".venv").join("Scripts").join("python.exe"));
        candidates.push(base.join("venv").join("Scripts").join("python.exe"));
    }
    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .unwrap_or_else(|| PathBuf::from("python"))
}

pub fn comfyui_process_spec(root: &Path) -> Result<ProcessSpec, String> {
    validate_comfyui_directory_path(root)?;
    if comfyui_entry_point(root).is_none() {
        let launcher = comfyui_launcher_batch(root).expect("validated ComfyUI launcher");
        return Ok(ProcessSpec {
            program: PathBuf::from("cmd.exe"),
            current_dir: root.to_path_buf(),
            args: [OsString::from("/C"), launcher.into_os_string()]
                .into_iter()
                .collect(),
        });
    }

    let entry = comfyui_entry_point(root).expect("validated ComfyUI entry point");
    let current_dir = entry
        .parent()
        .expect("ComfyUI entry point has a parent")
        .to_path_buf();
    let program = comfyui_python(root, &current_dir);

    Ok(ProcessSpec {
        program,
        current_dir,
        args: [
            "main.py",
            "--listen",
            "127.0.0.1",
            "--port",
            "8188",
            "--enable-manager",
        ]
        .into_iter()
        .map(OsString::from)
        .collect(),
    })
}

pub fn comfyui_manager_install_spec(root: &Path) -> Result<ProcessSpec, String> {
    validate_comfyui_directory_path(root)?;
    let entry = comfyui_entry_point(root)
        .ok_or_else(|| "当前 ComfyUI 启动方式不支持一键启用内置 Manager".to_string())?;
    let current_dir = entry
        .parent()
        .expect("ComfyUI entry point has a parent")
        .to_path_buf();
    let requirements = current_dir.join("manager_requirements.txt");
    if !requirements.is_file() {
        return Err("当前 ComfyUI 版本未包含 manager_requirements.txt，请先更新 ComfyUI".into());
    }

    Ok(ProcessSpec {
        program: comfyui_python(root, &current_dir),
        current_dir,
        args: [
            OsString::from("-m"),
            OsString::from("pip"),
            OsString::from("install"),
            OsString::from("-r"),
            requirements.into_os_string(),
        ]
        .into_iter()
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
    command
        .args(&spec.args)
        .current_dir(&spec.current_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
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

fn run_process_to_completion(spec: &ProcessSpec) -> Result<(), String> {
    let mut command = Command::new(&spec.program);
    command.args(&spec.args).current_dir(&spec.current_dir);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    let output = command.output().map_err(|error| {
        format!(
            "无法运行 {}：{error}",
            spec.program.as_os_str().to_string_lossy()
        )
    })?;
    if output.status.success() {
        return Ok(());
    }
    let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
    Err(if detail.is_empty() {
        format!("Manager 依赖安装失败：{}", output.status)
    } else {
        format!("Manager 依赖安装失败：{detail}")
    })
}

fn start_managed_comfyui(
    requested_root: &Path,
    processes: &ManagedProcesses,
) -> Result<u32, String> {
    validate_comfyui_directory_path(requested_root)?;
    let root = requested_root
        .canonicalize()
        .map_err(|error| format!("无法规范化 ComfyUI 目录：{error}"))?;
    let spec = comfyui_process_spec(&root)?;
    let mut children = processes
        .0
        .lock()
        .map_err(|_| "进程状态锁已损坏".to_string())?;
    let mut index = 0;
    while index < children.len() {
        if children[index].role != ProcessRole::Comfyui {
            index += 1;
            continue;
        }
        match children[index].child.try_wait() {
            Ok(None) => {
                let running_root = children[index]
                    .root
                    .as_deref()
                    .ok_or_else(|| "托管 ComfyUI 缺少根目录".to_string())?;
                match comfyui_start_decision(Some(running_root), &root) {
                    ComfyuiStartDecision::Reuse => {
                        return Ok(children[index].child.id());
                    }
                    ComfyuiStartDecision::Restart => {
                        terminate_process_tree(&mut children[index].child, Duration::from_secs(3))?;
                        children.remove(index);
                    }
                    ComfyuiStartDecision::Spawn => unreachable!("running root is present"),
                }
            }
            Ok(Some(_)) => {
                children.remove(index);
            }
            Err(error) => return Err(format!("无法检查托管进程状态：{error}")),
        }
    }

    let child = spawn_process(&spec)?;
    let process_id = child.id();
    children.push(ManagedProcess {
        role: ProcessRole::Comfyui,
        child,
        root: Some(root),
        agent_port: None,
    });
    Ok(process_id)
}

fn wait_for_process_exit(child: &mut Child, timeout: Duration) -> Result<(), String> {
    let deadline = Instant::now() + timeout;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => return Ok(()),
            Ok(None) if Instant::now() >= deadline => {
                return Err(format!("等待进程 {} 退出超时", child.id()));
            }
            Ok(None) => thread::sleep(Duration::from_millis(50)),
            Err(error) => return Err(format!("无法检查进程退出状态：{error}")),
        }
    }
}

#[cfg(windows)]
pub fn terminate_process_tree(child: &mut Child, timeout: Duration) -> Result<(), String> {
    use std::os::windows::process::CommandExt;

    if child
        .try_wait()
        .map_err(|error| format!("无法检查进程状态：{error}"))?
        .is_some()
    {
        return Ok(());
    }
    let process_id = child.id().to_string();
    let mut taskkill = Command::new("taskkill");
    taskkill
        .args(["/PID", process_id.as_str(), "/T", "/F"])
        .creation_flags(0x08000000);
    let taskkill_succeeded = taskkill
        .status()
        .map(|status| status.success())
        .unwrap_or(false);
    if !taskkill_succeeded {
        child
            .kill()
            .map_err(|error| format!("taskkill 失败，且无法终止进程 {}：{error}", child.id()))?;
    }
    wait_for_process_exit(child, timeout)
}

#[cfg(not(windows))]
pub fn terminate_process_tree(child: &mut Child, timeout: Duration) -> Result<(), String> {
    if child
        .try_wait()
        .map_err(|error| format!("无法检查进程状态：{error}"))?
        .is_none()
    {
        child
            .kill()
            .map_err(|error| format!("无法终止进程 {}：{error}", child.id()))?;
    }
    wait_for_process_exit(child, timeout)
}

fn stop_matching(processes: &ManagedProcesses, role: Option<ProcessRole>) -> Result<(), String> {
    let mut children = processes
        .0
        .lock()
        .map_err(|_| "进程状态锁已损坏".to_string())?;
    let mut errors = Vec::new();
    let mut index = 0;
    while index < children.len() {
        if role.is_some_and(|expected| children[index].role != expected) {
            index += 1;
            continue;
        }
        match terminate_process_tree(&mut children[index].child, Duration::from_secs(3)) {
            Ok(()) => {
                children.remove(index);
            }
            Err(error) => {
                errors.push(error);
                index += 1;
            }
        }
    }
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors.join("；"))
    }
}

fn stop_all(processes: &ManagedProcesses) -> Result<(), String> {
    stop_matching(processes, None)
}

fn stop_managed_comfyui(processes: &ManagedProcesses) -> Result<(), String> {
    stop_matching(processes, Some(ProcessRole::Comfyui))
}

fn agent_endpoint(pid: u32, port: u16) -> AgentEndpoint {
    AgentEndpoint {
        pid,
        port,
        base_url: format!("http://127.0.0.1:{port}"),
    }
}

fn start_local_agent_core<C, S, W>(
    children: &mut Vec<ManagedProcess<C>>,
    mut spawn: S,
    mut wait_for_startup: W,
) -> Result<AgentEndpoint, String>
where
    C: AgentChild,
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

    for port in 8000..=8099 {
        let mut child = spawn(port)?;
        wait_for_startup();
        match child.try_exit() {
            Ok(None) => {
                let endpoint = agent_endpoint(child.id(), port);
                children.push(ManagedProcess {
                    role: ProcessRole::Agent,
                    child,
                    root: None,
                    agent_port: Some(port),
                });
                return Ok(endpoint);
            }
            Ok(Some(_)) if port < 8099 => {}
            Ok(Some(status)) => {
                return Err(format!(
                    "Agent 无法绑定 8000 到 8099 端口（最后退出状态：{status}）"
                ));
            }
            Err(error) => {
                child.terminate(Duration::from_secs(3))?;
                return Err(format!("无法检查新启动的 Agent 进程状态：{error}"));
            }
        }
    }

    Err("Agent 无法绑定 8000 到 8099 端口".to_string())
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
async fn select_directory(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let Some(selection) = app.dialog().file().blocking_pick_folder() else {
        return Ok(None);
    };
    let path = selection.into_path().map_err(|error| error.to_string())?;
    Ok(Some(path.to_string_lossy().into_owned()))
}

#[tauri::command]
fn validate_comfyui_directory(path: String) -> Result<(), String> {
    validate_comfyui_directory_path(Path::new(&path))
}

#[tauri::command]
fn open_in_explorer(path: String) -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;

        Command::new("explorer.exe")
            .arg(format!("/select,{}", path))
            .creation_flags(0x08000000)
            .spawn()
            .map_err(|error| format!("无法打开文件夹：{error}"))?;
        Ok(())
    }
    #[cfg(not(windows))]
    {
        let _ = path;
        Err("当前平台不支持打开文件夹".into())
    }
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
    start_managed_comfyui(Path::new(&path), &processes)
}

#[tauri::command]
async fn enable_comfyui_manager(
    path: String,
    processes: State<'_, ManagedProcesses>,
) -> Result<u32, String> {
    let root = PathBuf::from(path);
    let install_spec = comfyui_manager_install_spec(&root)?;
    tauri::async_runtime::spawn_blocking(move || run_process_to_completion(&install_spec))
        .await
        .map_err(|error| format!("Manager 安装任务失败：{error}"))??;
    stop_managed_comfyui(&processes)?;
    start_managed_comfyui(&root, &processes)
}

#[tauri::command]
fn open_comfyui_manager(app: tauri::AppHandle, url: String) -> Result<(), String> {
    let target = validate_comfyui_web_url(&url)?;
    if let Some(window) = app.get_webview_window("comfyui-manager") {
        let current = window
            .url()
            .map_err(|error| format!("读取 ComfyUI 窗口地址失败：{error}"))?;
        if current == target {
            window
                .show()
                .map_err(|error| format!("显示 ComfyUI 窗口失败：{error}"))?;
            window
                .set_focus()
                .map_err(|error| format!("聚焦 ComfyUI 窗口失败：{error}"))?;
            return Ok(());
        }
        window
            .close()
            .map_err(|error| format!("关闭旧 ComfyUI 窗口失败：{error}"))?;
    }

    let window = WebviewWindowBuilder::new(
        &app,
        "comfyui-manager",
        WebviewUrl::External(target),
    )
    .title("ComfyUI 模型库")
    .inner_size(1280.0, 820.0)
    .min_inner_size(960.0, 640.0)
    .initialization_script(COMFYUI_MANAGER_LOADING_SCRIPT)
    .center()
    .build()
    .map_err(|error| format!("创建 ComfyUI 窗口失败：{error}"))?;
    window
        .set_focus()
        .map_err(|error| format!("聚焦 ComfyUI 窗口失败：{error}"))
}

#[tauri::command]
fn stop_comfyui(processes: State<'_, ManagedProcesses>) -> Result<(), String> {
    stop_managed_comfyui(&processes)
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
            select_directory,
            validate_comfyui_directory,
            open_in_explorer,
            start_local_agent,
            start_comfyui,
            enable_comfyui_manager,
            open_comfyui_manager,
            stop_comfyui,
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

    #[test]
    fn accepts_http_comfyui_urls_and_rejects_other_schemes() {
        assert_eq!(
            validate_comfyui_web_url("http://127.0.0.1:8188")
                .expect("valid ComfyUI URL")
                .as_str(),
            "http://127.0.0.1:8188/"
        );
        assert!(validate_comfyui_web_url("file:///tmp/index.html").is_err());
    }

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

        fn terminate(&mut self, _timeout: Duration) -> Result<(), String> {
            Ok(())
        }
    }

    #[test]
    fn reuses_the_saved_port_of_a_live_managed_agent() {
        let mut children = vec![ManagedProcess {
            role: ProcessRole::Agent,
            child: FakeAgentChild::running(52),
            root: None,
            agent_port: Some(8007),
        }];

        let endpoint = start_local_agent_core(
            &mut children,
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

    #[test]
    fn portable_comfyui_starts_with_the_builtin_manager_enabled() {
        let temporary = tempfile::tempdir().expect("temporary directory");
        let portable_root = temporary.path();
        let comfy_root = portable_root.join("ComfyUI");
        std::fs::create_dir_all(&comfy_root).expect("create ComfyUI directory");
        std::fs::write(comfy_root.join("main.py"), "").expect("create main.py");
        std::fs::write(
            comfy_root.join("manager_requirements.txt"),
            "comfyui_manager==4.1",
        )
        .expect("create manager requirements");
        std::fs::create_dir_all(portable_root.join("python_embeded"))
            .expect("create embedded Python directory");
        std::fs::write(portable_root.join("python_embeded").join("python.exe"), "")
            .expect("create embedded Python executable");

        let spec = comfyui_process_spec(portable_root).expect("portable process spec");

        assert!(spec.args.contains(&OsString::from("--enable-manager")));

        let install_spec = comfyui_manager_install_spec(portable_root)
            .expect("portable Manager install process spec");
        assert_eq!(
            install_spec.program,
            portable_root.join("python_embeded").join("python.exe")
        );
        assert_eq!(install_spec.args[0..4], ["-m", "pip", "install", "-r"]);
        assert_eq!(
            install_spec.args[4],
            comfy_root.join("manager_requirements.txt").into_os_string()
        );
    }

    #[cfg(windows)]
    #[test]
    fn background_process_receives_valid_null_standard_handles() {
        let script = r#"
Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class NativeFileType { [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int nStdHandle); [DllImport("kernel32.dll")] public static extern uint GetFileType(IntPtr hFile); }'
$handleTypes = -10, -11, -12 | ForEach-Object { [NativeFileType]::GetFileType([NativeFileType]::GetStdHandle($_)) }
if ($handleTypes -notcontains 2) { exit 1 }
if ($handleTypes | Where-Object { $_ -ne 2 }) { exit 1 }
"#;
        let spec = ProcessSpec {
            program: PathBuf::from("powershell.exe"),
            args: ["-NoProfile", "-Command", script]
                .into_iter()
                .map(OsString::from)
                .collect(),
            current_dir: std::env::temp_dir(),
        };

        let status = spawn_process(&spec)
            .expect("spawn background process")
            .wait()
            .expect("wait for background process");

        assert!(
            status.success(),
            "background standard handles must point to NUL"
        );
    }
}
