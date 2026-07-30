# AI Art Agent MVP Implementation Plan

**Goal:** Build a Windows desktop application that configures a local or
remote ComfyUI instance and completes a text-to-image generation flow without
exposing nodes.

**Architecture:** A concentrated Vue 3 interface in `App.vue` runs inside
Tauri and talks to a focused FastAPI Agent in `backend/app/main.py`. Small
supporting modules own typed API calls, settings persistence, the ComfyUI
gateway, workflow transformation, schemas, and history. This concentrated
MVP architecture was explicitly approved; the earlier proposed Pinia stores,
Vue Router views, route modules, and `GenerationService` abstraction were not
needed and were not implemented.

**Tech Stack:** Tauri 2, Rust, Vue 3, TypeScript, Vite, Vitest, CSS, Python
3.11+, FastAPI, Pydantic 2, httpx, and pytest.

**Status:** Complete (2026-07-30)

## Verification Record

- Backend unit and API integration tests: verified.
- Frontend component tests and production build: verified.
- Rust unit and desktop integration tests: verified.
- Mocked end-to-end flow (configure, checkpoint, submit, complete, history):
  verified.
- Live ComfyUI text-to-image flow and persisted history: verified.
- PyInstaller Agent packaging and process smoke test: verified.
- Tauri release executable smoke test: verified.
- Final NSIS installer artifact and installed launch flow: verified.
- NSIS-only packaging supersedes the early MSI/NSIS dual-output proposal.

## Approved MVP Structure

- `backend/app/main.py`: concentrated FastAPI routes and task reconciliation.
- `backend/app/settings.py`, `schemas.py`, and `history.py`: persistence and
  data contracts.
- `backend/app/comfy/`: ComfyUI gateway and workflow transformation.
- `backend/tests/`: mocked gateway, API, persistence, and workflow tests.
- `frontend/src/App.vue`: settings, generation, polling, results, and history.
- `frontend/src/lib/api.ts` and `desktop.ts`: typed HTTP and Tauri boundaries.
- `frontend/src/*.css`: responsive visual styling.
- `src-tauri/src/lib.rs`: native process lifecycle and desktop commands.
- `workflows/text-to-image.json`: packaged immutable workflow template.

## Completed Tasks

### Task 1: Backend Foundation and Settings

- [x] Implement `AppConfig`, atomic JSON configuration storage, schemas, and
  health/config routes.
- [x] Verify default settings, persistence, desktop health identity, and CORS.

### Task 2: ComfyUI Gateway and Workflow Builder

- [x] Implement ComfyUI status, checkpoint, queue, history, and prompt APIs.
- [x] Implement immutable text-to-image workflow parameter replacement.
- [x] Verify the gateway with mocked HTTP transport and workflow fixtures.

### Task 3: Task Execution and History

- [x] Implement generation submission, runtime task reconciliation, output
  URLs, execution errors, cancellation detection, and persisted history in
  the approved concentrated backend.
- [x] Verify queued, pending, running, completed, failed, transient gateway,
  and multi-output behavior.

### Task 4: Frontend Foundation and Settings Flow

- [x] Implement the typed API client and accessible local/remote settings form
  directly in the concentrated Vue application.
- [x] Implement candidate connection testing without persistence and native
  ComfyUI lifecycle ordering around configuration saves.
- [x] Verify validation, directory selection, save failure, reuse, remote
  stop, and connection state.

### Task 5: Generation, Progress, and History UI

- [x] Implement generation parameters, checkpoint selection, resilient polling
  with bounded backoff, terminal error display, multi-image results, and
  multi-image history in `App.vue`.
- [x] Verify submission, recovery after temporary gateway errors, execution
  errors, result galleries, and persisted history cards.

### Task 6: Tauri Desktop Integration

- [x] Implement directory validation/selection, dynamic Agent ports, managed
  ComfyUI reuse/restart/stop, and bounded process-tree cleanup.
- [x] Verify native command specs, lifecycle decisions, port recovery, and
  cleanup deadlines with Rust tests.

### Task 7: End-to-End Verification and Packaging

- [x] Verify backend, frontend, Rust, and production frontend build commands.
- [x] Verify the mocked end-to-end flow and live ComfyUI generation flow.
- [x] Verify packaged Agent startup, Tauri release smoke, and the final
  NSIS-only installer.
- [x] Document setup, local/remote modes, development commands, and MVP
  limitations.
