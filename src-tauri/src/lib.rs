use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, State};
use tauri_plugin_dialog::DialogExt;

#[derive(Debug, PartialEq, Eq)]
pub struct ProcessSpec {
    pub program: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum ProcessRole {
    Agent,
    Comfyui,
}

struct ManagedProcess {
    role: ProcessRole,
    child: Child,
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

fn local_agent_process_spec(app: &tauri::AppHandle) -> Result<ProcessSpec, String> {
    if cfg!(debug_assertions) {
        let backend = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../backend");
        let virtualenv_python = backend.join(".venv").join("Scripts").join("python.exe");
        return Ok(ProcessSpec {
            program: if virtualenv_python.is_file() {
                virtualenv_python
            } else {
                PathBuf::from("python")
            },
            current_dir: backend,
            args: [
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ]
            .into_iter()
            .map(OsString::from)
            .collect(),
        });
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
        args: Vec::new(),
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
    children.push(ManagedProcess { role, child });
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

#[tauri::command]
async fn select_comfyui_directory(
    app: tauri::AppHandle,
) -> Result<Option<String>, String> {
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
) -> Result<u32, String> {
    spawn_managed(
        local_agent_process_spec(&app)?,
        ProcessRole::Agent,
        true,
        &processes,
    )
}

#[tauri::command]
fn start_comfyui(
    path: String,
    processes: State<'_, ManagedProcesses>,
) -> Result<u32, String> {
    spawn_managed(
        comfyui_process_spec(Path::new(&path))?,
        ProcessRole::Comfyui,
        false,
        &processes,
    )
}

#[tauri::command]
fn stop_managed_processes(
    processes: State<'_, ManagedProcesses>,
) -> Result<(), String> {
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
