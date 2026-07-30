use std::ffi::OsString;
use std::fs;

use ai_art_agent_lib::{
    comfyui_process_spec, debug_agent_process_spec, packaged_agent_process_spec, select_agent_port,
    validate_comfyui_directory_path,
};
use tempfile::tempdir;

#[test]
fn rejects_a_directory_without_a_comfyui_entry_point() {
    let root = tempdir().expect("temporary directory");

    let error = validate_comfyui_directory_path(root.path()).unwrap_err();

    assert!(error.contains("main.py"));
}

#[test]
fn accepts_a_standard_comfyui_checkout() {
    let root = tempdir().expect("temporary directory");
    fs::write(root.path().join("main.py"), "").expect("create entry point");

    validate_comfyui_directory_path(root.path()).expect("valid ComfyUI directory");
}

#[test]
fn builds_the_portable_comfyui_command_from_the_selected_root() {
    let root = tempdir().expect("temporary directory");
    let comfy_dir = root.path().join("ComfyUI");
    let embedded_python = root.path().join("python_embeded").join("python.exe");
    fs::create_dir_all(&comfy_dir).expect("create ComfyUI directory");
    fs::create_dir_all(embedded_python.parent().unwrap()).expect("create Python directory");
    fs::write(comfy_dir.join("main.py"), "").expect("create entry point");
    fs::write(&embedded_python, "").expect("create embedded Python");

    let spec = comfyui_process_spec(root.path()).expect("portable process spec");

    assert_eq!(spec.program, embedded_python);
    assert_eq!(spec.current_dir, comfy_dir);
    assert_eq!(
        spec.args,
        vec![
            OsString::from("main.py"),
            OsString::from("--listen"),
            OsString::from("127.0.0.1"),
            OsString::from("--port"),
            OsString::from("8188"),
        ]
    );
}

#[test]
fn uses_a_standard_checkouts_virtual_environment() {
    let root = tempdir().expect("temporary directory");
    let virtualenv_python = root.path().join(".venv").join("Scripts").join("python.exe");
    fs::create_dir_all(virtualenv_python.parent().unwrap()).expect("create virtualenv");
    fs::write(root.path().join("main.py"), "").expect("create entry point");
    fs::write(&virtualenv_python, "").expect("create virtualenv Python");

    let spec = comfyui_process_spec(root.path()).expect("standard process spec");

    assert_eq!(spec.program, virtualenv_python);
    assert_eq!(spec.current_dir, root.path());
}

#[test]
fn selects_the_first_available_agent_port() {
    let selected = select_agent_port(|port| port == 8002).expect("available port");

    assert_eq!(selected, 8002);
}

#[test]
fn reports_when_the_agent_port_range_is_exhausted() {
    let error = select_agent_port(|_| false).unwrap_err();

    assert!(error.contains("8000"));
    assert!(error.contains("8099"));
}

#[test]
fn builds_the_debug_agent_command_with_the_selected_port() {
    let spec = debug_agent_process_spec(8007);

    assert_eq!(
        spec.args,
        vec![
            OsString::from("-m"),
            OsString::from("uvicorn"),
            OsString::from("app.main:app"),
            OsString::from("--host"),
            OsString::from("127.0.0.1"),
            OsString::from("--port"),
            OsString::from("8007"),
        ]
    );
}

#[test]
fn builds_the_packaged_agent_command_with_the_selected_port() {
    let backend_dir = tempdir().expect("temporary backend directory");
    let executable = backend_dir.path().join("ai-art-agent-backend.exe");
    fs::write(&executable, "").expect("create packaged agent executable");

    let spec =
        packaged_agent_process_spec(backend_dir.path(), 8008).expect("packaged process spec");

    assert_eq!(spec.program, executable);
    assert_eq!(
        spec.args,
        vec![OsString::from("--port"), OsString::from("8008")]
    );
}
