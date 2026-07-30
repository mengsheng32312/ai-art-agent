# MVP Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the reviewed desktop-port, ComfyUI lifecycle, connection-test, generation polling, multi-output, and process-cleanup defects without restructuring the MVP.

**Architecture:** Keep the existing focused FastAPI application and Vue `App.vue`, but add explicit runtime contracts at their boundaries. Tauri selects and returns the desktop Agent endpoint, FastAPI owns candidate connection checks and task-state reconciliation, and the Vue client consumes those contracts while preserving the current single-page layout.

**Tech Stack:** Tauri 2, Rust 2021, Vue 3, TypeScript, Vitest, FastAPI, Pydantic 2, pytest

## Global Constraints

- Target Windows 10 and Windows 11.
- Scan only `127.0.0.1:8000` through `127.0.0.1:8099` for the desktop Agent.
- Do not persist the selected desktop Agent port in user configuration.
- Do not stop ComfyUI processes that were not started by this application.
- Preserve existing configuration and history JSON compatibility.
- Do not refactor the MVP into Pinia stores, Vue Router views, backend route modules, or a new service layer.
- Do not change the ComfyUI workflow JSON or add model/node downloads.
- Follow test-driven development for every behavior change.

---

### Task 1: Dynamic Desktop Agent Endpoint

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_health.py`
- Modify: `backend/tests/test_desktop_entry.py`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/tests/desktop.rs`
- Modify: `frontend/src/lib/desktop.ts`
- Modify: `frontend/src/lib/desktop.test.ts`

**Interfaces:**
- Produces: `GET /api/health -> {"status":"ok","service":"ai-art-agent","version":"0.1.0"}`.
- Produces: `start_local_agent -> AgentEndpoint { pid: u32, port: u16, base_url: String }`.
- Produces: `agentApiBase()` using the runtime desktop endpoint or `/api` in browser mode.
- Consumes: backend command-line option `--port <8000..8099>`.

- [x] **Step 1: Add failing backend contract tests**

Update the health assertion to:

```python
assert response.json() == {
    "status": "ok",
    "service": "ai-art-agent",
    "version": "0.1.0",
}
```

Replace the fixed-port desktop-entry test with:

```python
monkeypatch.setattr(sys, "argv", ["ai-art-agent-backend", "--port", "8007"])
app_main.run()
assert captured["options"] == {"host": "127.0.0.1", "port": 8007}
```

Run:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_health.py backend\tests\test_desktop_entry.py -v
```

Expected: FAIL because health lacks identity fields and `run()` ignores `--port`.

- [x] **Step 2: Implement the backend contract**

In `backend/app/main.py`, return the three health fields and parse the desktop port:

```python
def desktop_port(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, default=8000)
    options, _ = parser.parse_known_args(argv)
    if not 8000 <= options.port <= 8099:
        raise ValueError("Agent 端口必须在 8000 到 8099 之间")
    return options.port


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=desktop_port())
```

Run the focused backend tests and confirm PASS.

- [x] **Step 3: Add failing Rust port-selection tests**

Expose a pure selector:

```rust
pub fn select_agent_port<F>(mut is_available: F) -> Result<u16, String>
where
    F: FnMut(u16) -> bool;
```

Add tests proving it skips occupied ports and errors after 8099:

```rust
assert_eq!(select_agent_port(|port| port == 8002).unwrap(), 8002);
assert!(select_agent_port(|_| false).unwrap_err().contains("8000"));
```

Also assert the packaged/debug Agent spec includes `--port` and the selected value.

Run:

```text
cargo test --manifest-path src-tauri/Cargo.toml --offline
```

Expected: FAIL because the selector and port-aware spec do not exist.

- [x] **Step 4: Implement dynamic selection and endpoint return**

Add:

```rust
#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct AgentEndpoint {
    pid: u32,
    port: u16,
    base_url: String,
}
```

Use `TcpListener::bind(("127.0.0.1", port))` as the production availability predicate. Build both debug and packaged commands with `--port <selected>`. After spawning, wait briefly and use `try_wait()`; if a port race makes the child exit, clean it up and continue with the next candidate. Return an error after 8099.

Store the selected port on the managed Agent process:

```rust
struct ManagedProcess {
    role: ProcessRole,
    child: Child,
    root: Option<PathBuf>,
    agent_port: Option<u16>,
}
```

When the current managed Agent is still alive, return an `AgentEndpoint` reconstructed from its stored port instead of selecting or spawning again.

Run the Rust tests and confirm PASS.

- [x] **Step 5: Add failing frontend bootstrap tests**

Change the Tauri mock to return:

```ts
{ pid: 42, port: 8001, baseUrl: "http://127.0.0.1:8001" }
```

Add assertions that:

```ts
expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8001/api/health")
```

and a 200 response with `{"status":"ok"}` but no matching `service` does not finish bootstrap.

Run:

```powershell
npm.cmd --prefix frontend test -- --run frontend/src/lib/desktop.test.ts
```

Expected: FAIL because the base URL is fixed and health JSON is not validated.

- [x] **Step 6: Implement the runtime frontend endpoint**

Store the endpoint only in module memory:

```ts
type AgentEndpoint = { pid: number; port: number; baseUrl: string }
let desktopAgentBase: string | null = null

export function agentApiBase(): string {
  return isDesktop() && desktopAgentBase
    ? `${desktopAgentBase}/api`
    : "/api"
}
```

`startDesktopAgent()` must set `desktopAgentBase` from the Tauri response. `prepareDesktopAgent()` must parse the health JSON and accept only `status === "ok"`, `service === "ai-art-agent"`, and `version === "0.1.0"`.

Run the focused frontend tests and confirm PASS.

- [x] **Step 7: Commit Task 1**

```powershell
git add backend/app/main.py backend/tests/test_health.py backend/tests/test_desktop_entry.py src-tauri/src/lib.rs src-tauri/tests/desktop.rs frontend/src/lib/desktop.ts frontend/src/lib/desktop.test.ts
git commit -m "fix: select a safe desktop agent port"
```

---

### Task 2: Candidate Connection and ComfyUI Lifecycle

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_generation.py`
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/tests/desktop.rs`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/desktop.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Produces: `POST /api/comfy/status` accepting an `AppConfig` without persisting it.
- Produces: `stop_comfyui` Tauri command.
- Produces: same-path ComfyUI reuse and different-path managed restart.
- Consumes: the current settings form as the candidate connection configuration.

- [x] **Step 1: Add failing candidate-connection API tests**

Use a factory that records the URL it receives:

```python
seen_urls: list[str] = []

def factory(url: str):
    seen_urls.append(url)
    return FakeComfyClient()
```

POST a candidate remote config to `/api/comfy/status`, assert the candidate URL is checked, then GET `/api/config` and assert the candidate was not persisted.

Add a failure test whose fake client raises and assert:

```json
{"connected": false, "message": "..."}
```

Run the focused test and confirm it fails because POST is unsupported.

- [x] **Step 2: Implement candidate checking**

Extract:

```python
async def connection_status(config: AppConfig) -> ConnectionStatus:
    try:
        await comfy_factory(config.api_url).check_status()
        return ConnectionStatus(connected=True, message="ComfyUI 已连接")
    except Exception as exc:
        return ConnectionStatus(connected=False, message=str(exc))
```

Keep GET `/api/comfy/status` for saved config and add POST for the supplied `AppConfig`. Confirm the focused backend tests pass.

- [x] **Step 3: Add failing Rust lifecycle-decision tests**

Extend `ManagedProcess` with:

```rust
root: Option<PathBuf>
```

Extract and test a pure decision:

```rust
pub enum ComfyuiStartDecision { Spawn, Reuse, Restart }
pub fn comfyui_start_decision(
    running_root: Option<&Path>,
    requested_root: &Path,
) -> ComfyuiStartDecision;
```

Assert no current root means `Spawn`, equal normalized roots mean `Reuse`, and a different root means `Restart`.

Run Rust tests and confirm RED.

- [x] **Step 4: Implement managed ComfyUI reuse, restart, and stop**

Normalize requested roots with `canonicalize()` after validation. For an alive managed ComfyUI:

- same root: return its PID;
- different root: stop the existing managed ComfyUI through the role-specific cleanup path, remove it, then spawn; Task 4 hardens that shared cleanup path with a deadline;
- exited child: remove it, then spawn.

Add:

```rust
#[tauri::command]
fn stop_comfyui(processes: State<'_, ManagedProcesses>) -> Result<(), String>
```

It must stop only `ProcessRole::Comfyui`. Register it in `generate_handler!`. Run Rust tests and confirm PASS.

- [x] **Step 5: Add failing frontend settings tests**

Extend the API mock with `checkStatus`. Add tests proving:

- “测试连接” passes the current unsaved form to `api.checkStatus(config)`;
- local save calls `start_comfyui` before `saveConfig`;
- remote save calls `stop_comfyui` before `saveConfig`;
- a native start failure means `saveConfig` is not called;
- saving the same local path remains successful when native start returns the existing PID.

Run `frontend/src/App.test.ts` and confirm RED.

- [x] **Step 6: Implement the settings flow**

Add:

```ts
checkStatus: (config: Config) =>
  request<ConnectionStatus>("/comfy/status", {
    method: "POST",
    body: JSON.stringify(config),
  })
```

Add `stopComfyui()` in `desktop.ts`. Split the UI actions:

```ts
async function testConnection() {
  const state = await api.checkStatus({ ...config })
  // update connection state and checkpoints only; do not save
}
```

For save:

1. local: set local API URL, start/reuse ComfyUI, then save;
2. remote: stop managed ComfyUI, then save;
3. refresh the saved connection after success.

Run the focused frontend tests and confirm PASS.

- [x] **Step 7: Include Task 2 in the combined Task 2–4 commit**

The individual Task 2 commit was superseded by the user-requested combined
Task 2–4 change set.

---

### Task 3: Resilient Generation Polling and Multi-Image Results

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_generation.py`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`
- Modify: `frontend/src/style.css`
- Modify: `frontend/src/media.css`

**Interfaces:**
- Produces: three-strike missing-task terminal failure.
- Produces: structured HTTP 502 for temporary ComfyUI status failures.
- Produces: retrying frontend poll loop with a 5-second maximum delay.
- Produces: all `GenerationTask.outputs` rendered in current results and history.

- [x] **Step 1: Add failing backend reconciliation tests**

Add tests proving:

```python
# missing from history, queue_running, and queue_pending
assert first.status_code == 200 and first.json()["status"] == "queued"
assert second.status_code == 200 and second.json()["status"] == "queued"
assert third.json()["status"] == "failed"
assert "取消或中断" in third.json()["error"]
```

Add a pending-queue test that remains `queued`, and a gateway-exception test that returns 502 with a Chinese `detail` and does not consume a missing strike.

Run focused backend tests and confirm RED.

- [x] **Step 2: Implement task reconciliation**

Inside `create_app`, keep runtime-only counters:

```python
missing_polls: dict[str, int] = {}
```

On each active-task poll:

- history output/error: complete/fail and remove its counter;
- `queue_running`: mark running and reset counter;
- `queue_pending`: keep queued and reset counter;
- missing everywhere: increment; fail at 3 with `任务已从 ComfyUI 队列消失，可能已取消或中断`;
- gateway exception: raise `HTTPException(502, "暂时无法读取 ComfyUI 任务状态")` without modifying the counter.

Run the focused backend tests and confirm PASS.

- [x] **Step 3: Add failing frontend retry and gallery tests**

With fake timers, make `api.generation` reject once and then return completed. Assert polling retries and the final image appears.

Add a completed task with:

```ts
outputs: [
  "http://comfy/view?filename=fox-1.png",
  "http://comfy/view?filename=fox-2.png",
]
```

Assert two current-result images with numbered alt text and two history images are rendered.

Run `frontend/src/App.test.ts` and confirm RED.

- [x] **Step 4: Implement retrying polling**

Move the per-request error handling inside the polling loop:

```ts
let failures = 0
while (currentTask.value && !["completed", "failed"].includes(currentTask.value.status)) {
  await delay(failures ? Math.min(1000 * 2 ** failures, 5000) : 1000)
  try {
    currentTask.value = await api.generation(task.id)
    failures = 0
  } catch (error) {
    failures += 1
    notice.value = `任务状态暂时无法更新，正在重试：${message(error)}`
    continue
  }
}
```

Successful polling clears the temporary retry notice. A backend terminal failure still ends the loop and displays its stored error.

- [x] **Step 5: Render all outputs**

Replace fixed `[0]` rendering with:

```vue
<div v-if="currentTask?.outputs.length" class="result-gallery">
  <img
    v-for="(output, index) in currentTask.outputs"
    :key="output"
    :src="output"
    :alt="`生成结果 ${index + 1}`"
  />
</div>
```

Render each history task's outputs in a `.thumb-grid` using `历史生成结果 ${index + 1}`. Add responsive CSS grids; one image must retain the current full preview appearance.

Run focused frontend tests and confirm PASS.

- [x] **Step 6: Include Task 3 in the combined Task 2–4 commit**

The individual Task 3 commit was superseded by the user-requested combined
Task 2–4 change set.

---

### Task 4: Bounded Process Cleanup and Plan Reconciliation

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/tests/desktop.rs`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `docs/superpowers/plans/2026-07-29-ai-art-agent-mvp.md`
- Modify: `docs/superpowers/plans/2026-07-30-mvp-boundary-hardening.md`

**Interfaces:**
- Produces: `terminate_process_tree(child, timeout) -> Result<(), String>`.
- Produces: explicit cleanup failures instead of unbounded waits.
- Removes: unused Pinia initialization and dependency.

- [x] **Step 1: Add a failing bounded-cleanup Rust test**

On Windows, spawn a disposable long-running command:

```rust
let mut child = Command::new("cmd")
    .args(["/C", "ping 127.0.0.1 -n 30 >NUL"])
    .spawn()
    .unwrap();
let started = Instant::now();
terminate_process_tree(&mut child, Duration::from_secs(3)).unwrap();
assert!(started.elapsed() < Duration::from_secs(5));
assert!(child.try_wait().unwrap().is_some());
```

Run Rust tests and confirm RED because cleanup has no result or timeout.

- [x] **Step 2: Implement bounded cleanup**

Make `terminate_process_tree` return `Result<(), String>`.

On Windows:

1. run `taskkill /PID <pid> /T /F`;
2. if launch fails or exit status is unsuccessful, call `child.kill()`;
3. poll `child.try_wait()` every 50 ms until the deadline;
4. return a Chinese timeout/error instead of calling unbounded `wait()`.

On non-Windows, call `kill()` and use the same bounded polling helper. Update role-specific and all-process cleanup to collect and return errors.

Run Rust tests and confirm PASS.

- [x] **Step 3: Remove unused Pinia**

Change:

```ts
createApp(App).mount("#app")
```

Remove `pinia` from `frontend/package.json` using:

```powershell
npm.cmd --prefix frontend uninstall pinia
```

Run:

```powershell
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run build
```

Expected: all frontend tests and the production build pass.

- [x] **Step 4: Reconcile the implementation plan**

Update the original plan to:

- set status to complete on 2026-07-30;
- record backend, frontend, Rust, mocked E2E, release smoke, and final NSIS verification;
- replace the planned-but-unused store/view/service file structure with the approved concentrated MVP structure;
- state that NSIS-only supersedes MSI/NSIS dual output;
- mark Tasks 1–7 complete without claiming unimplemented abstractions.

Mark every completed checkbox in this hardening plan only after its command evidence exists.

- [x] **Step 5: Run the final focused regression**

Run once after all tasks:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests\test_generation.py backend\tests\test_health.py -v
npm.cmd --prefix frontend test -- --run src/App.test.ts src/lib/desktop.test.ts
npm.cmd --prefix frontend run build
cargo test --manifest-path src-tauri\Cargo.toml --offline --lib --test desktop
```

Expected: backend, frontend, build, and Rust all pass. Do not rebuild or reinstall NSIS unless a packaging/resource file changed.

- [x] **Step 6: Create the combined Task 2–4 commit**

```powershell
git add backend frontend src-tauri docs/superpowers/plans/2026-07-29-ai-art-agent-mvp.md docs/superpowers/plans/2026-07-30-mvp-boundary-hardening.md
git commit -m "fix: harden MVP runtime boundaries"
```
