# AI Art Agent MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows desktop application that configures a local or remote ComfyUI instance and completes a text-to-image generation flow without exposing nodes.

**Architecture:** A Vue 3 interface runs inside Tauri and communicates with a focused FastAPI local agent. The agent owns configuration, workflow construction, ComfyUI communication, task tracking, and history; ComfyUI remains an independent inference engine.

**Tech Stack:** Tauri 2, Vue 3, TypeScript, Vite, Tailwind CSS, shadcn-vue styling conventions, Pinia, Vitest, Python 3.11+, FastAPI, Pydantic 2, httpx, pytest.

## Global Constraints

- Target Windows 10 and Windows 11.
- Support local ComfyUI directory and remote ComfyUI API modes.
- Do not expose ComfyUI nodes or workflow JSON in the normal UI.
- Do not download models in the MVP.
- Store configuration and history under the operating system application-data directory.

---

## File Structure

- `frontend/`: Vue application, typed API client, stores, pages, and UI components.
- `src-tauri/`: Tauri configuration and commands for directory selection and process control.
- `backend/app/`: FastAPI application organized by configuration, ComfyUI gateway, workflows, tasks, and history.
- `backend/tests/`: unit and API integration tests using a mocked ComfyUI transport.
- `workflows/text-to-image.json`: built-in ComfyUI API workflow template.

### Task 1: Backend Foundation and Settings

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/main.py`
- Create: `backend/app/settings.py`
- Create: `backend/app/schemas.py`
- Test: `backend/tests/test_settings.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `AppConfig`, `ConfigStore.load()`, `ConfigStore.save(config)`, `GET /api/health`, `GET/PUT /api/config`.

- [ ] Write failing tests proving default remote URL is `http://127.0.0.1:8188`, config round-trips to JSON, and health returns `{"status":"ok"}`.
- [ ] Run `python -m pytest backend/tests/test_settings.py backend/tests/test_health.py -v` and confirm failure.
- [ ] Implement Pydantic schemas, atomic JSON configuration storage, and FastAPI routes.
- [ ] Run the tests and confirm they pass.
- [ ] Commit with `feat: add agent configuration foundation`.

### Task 2: ComfyUI Gateway and Workflow Builder

**Files:**
- Create: `backend/app/comfy/client.py`
- Create: `backend/app/comfy/workflow.py`
- Create: `workflows/text-to-image.json`
- Test: `backend/tests/test_comfy_client.py`
- Test: `backend/tests/test_workflow.py`

**Interfaces:**
- Produces: `ComfyClient.check_status()`, `ComfyClient.list_checkpoints()`, `ComfyClient.queue_prompt(workflow, client_id)`, `build_text_to_image_workflow(request)`.

- [ ] Write failing tests with `httpx.MockTransport` for `/system_stats`, `/object_info/CheckpointLoaderSimple`, and `/prompt`.
- [ ] Write a failing workflow test asserting prompt text, checkpoint, dimensions, seed, steps, CFG, sampler, scheduler, batch size, and output prefix are replaced.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement the async gateway and immutable workflow-template transformation.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit with `feat: add ComfyUI gateway and workflow builder`.

### Task 3: Task Execution and History

**Files:**
- Create: `backend/app/tasks/models.py`
- Create: `backend/app/tasks/service.py`
- Create: `backend/app/history.py`
- Create: `backend/app/routes/generation.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_generation.py`
- Test: `backend/tests/test_history.py`

**Interfaces:**
- Produces: `POST /api/generations`, `GET /api/generations/{id}`, `GET /api/history`, `GenerationService.submit(request)`.

- [ ] Write failing tests for queued, running, completed, and failed task states plus persisted history after store recreation.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement UUID task IDs, task-state transitions, output references, bounded history, and API routes.
- [ ] Run the focused tests and confirm they pass.
- [ ] Commit with `feat: add generation tasks and history`.

### Task 4: Frontend Foundation and Settings Flow

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/stores/settings.ts`
- Create: `frontend/src/views/SettingsView.vue`
- Test: `frontend/src/views/SettingsView.test.ts`

**Interfaces:**
- Produces: typed `agentApi`, `useSettingsStore()`, local/remote configuration form and connection test.

- [ ] Write a failing component test for switching modes, validating required fields, saving settings, and displaying connection state.
- [ ] Run `npm --prefix frontend test -- --run` and confirm failure.
- [ ] Scaffold Vue, TypeScript, Pinia, Vue Router, Tailwind tokens, and reusable shadcn-style primitives.
- [ ] Implement the typed API client, settings store, and accessible settings form.
- [ ] Run frontend tests and confirm they pass.
- [ ] Commit with `feat: add desktop settings experience`.

### Task 5: Generation, Progress, and History UI

**Files:**
- Create: `frontend/src/stores/generation.ts`
- Create: `frontend/src/views/GenerateView.vue`
- Create: `frontend/src/views/HistoryView.vue`
- Create: `frontend/src/components/GenerationForm.vue`
- Create: `frontend/src/components/GenerationResult.vue`
- Test: `frontend/src/components/GenerationForm.test.ts`
- Test: `frontend/src/views/HistoryView.test.ts`

**Interfaces:**
- Consumes: `agentApi`, config connection state, generation and history endpoints.
- Produces: complete text-to-image user flow.

- [ ] Write failing tests for checkpoint selection, basic and advanced parameters, disabled submission while disconnected, progress polling, error display, and persisted result cards.
- [ ] Run frontend tests and confirm failure.
- [ ] Implement the generation store, form, status panel, result preview, and history grid.
- [ ] Run frontend tests and confirm they pass.
- [ ] Commit with `feat: add generation and history interface`.

### Task 6: Tauri Desktop Integration

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/capabilities/default.json`
- Modify: `frontend/src/stores/settings.ts`
- Test: `src-tauri/src/lib.rs`

**Interfaces:**
- Produces: `select_comfyui_directory`, `validate_comfyui_directory`, `start_local_agent`, `start_comfyui`, and `stop_managed_processes` commands.

- [ ] Write Rust unit tests for directory validation and command argument construction.
- [ ] Run `cargo test --manifest-path src-tauri/Cargo.toml` and confirm failure.
- [ ] Implement narrowly scoped Tauri commands and process lifecycle cleanup.
- [ ] Connect the settings page to the native directory picker when running under Tauri.
- [ ] Run Rust and frontend tests and confirm they pass.
- [ ] Commit with `feat: integrate Windows desktop controls`.

### Task 7: End-to-End Verification and Packaging

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `scripts/dev.ps1`
- Create: `scripts/verify.ps1`
- Modify: `frontend/package.json`
- Modify: `src-tauri/tauri.conf.json`

**Interfaces:**
- Produces: documented local development flow and Windows installer build.

- [ ] Run all backend tests with `python -m pytest backend/tests -v`.
- [ ] Run all frontend tests and production build with `npm --prefix frontend test -- --run` and `npm --prefix frontend run build`.
- [ ] Run `cargo test --manifest-path src-tauri/Cargo.toml`.
- [ ] Run the mocked end-to-end flow: configure, list checkpoint, submit, complete, view history.
- [ ] Build the Tauri application and verify it launches on Windows.
- [ ] Document setup, local and remote connection modes, development commands, and MVP limitations.
- [ ] Commit with `docs: add setup and verified desktop build`.
