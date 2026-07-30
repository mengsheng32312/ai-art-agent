# AI Art Agent Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate the approved minimal AI Art Agent application icon and provide the PNG/ICO assets required by the Tauri Windows build.

**Architecture:** Use the built-in image generation tool for one square source image, save the selected result in `src-tauri/icons/`, and use Pillow only for deterministic multi-size ICO conversion. The existing Tauri configuration continues to consume `icons/icon.ico`.

**Tech Stack:** Built-in image generation, PNG, Windows ICO, Pillow 12.2, Tauri 2

## Global Constraints

- Use the approved design in `docs/superpowers/specs/2026-07-30-ai-art-agent-icon-design.md`.
- Keep the icon visually simple; it is a build-enabling MVP asset, not a broader branding project.
- Do not add text, letters, people, photographic detail, or additional visual assets.
- Preserve the existing `src-tauri/tauri.conf.json` icon path.

---

### Task 1: Generate and Package the Application Icon

**Files:**
- Create: `src-tauri/icons/icon.png`
- Create: `src-tauri/icons/icon.ico`
- Verify: `src-tauri/tauri.conf.json`

**Interfaces:**
- Consumes: Tauri bundle icon path `icons/icon.ico`.
- Produces: a 1024×1024 PNG source and a Windows ICO containing 16, 24, 32, 48, 64, 128, and 256 pixel frames.

- [x] **Step 1: Record the existing failing build evidence**

Run the current offline Rust test command in the initialized Visual Studio x64 environment.

Expected: FAIL from `tauri-build` because `src-tauri/icons/icon.ico` does not exist.

- [x] **Step 2: Generate the approved source image**

Use the built-in image generation tool with this prompt:

```text
Use case: logo-brand
Asset type: Windows desktop application icon
Primary request: Create a clean modern icon for AI Art Agent.
Subject: A centered four-point sparkle fused with one minimal painterly brush stroke beneath it.
Style/medium: polished vector-friendly app icon, bold simple geometry, crisp edges, limited depth.
Composition/framing: centered on a dark navy rounded-square background with generous safe padding; recognizable at 16×16.
Color palette: background #0B1020; electric blue to violet gradient on the sparkle and brush stroke; a very small pale blue-white highlight at the sparkle center.
Constraints: square 1024×1024, no text, no letters, no people, no watermark, no photographic texture, no tiny decorative details, no extra objects.
```

Inspect the result and reject it if it contains text, extra objects, weak centering, or details that disappear at small sizes.

- [x] **Step 3: Save the PNG in the project**

Copy the selected built-in output to:

```text
src-tauri/icons/icon.png
```

Confirm the saved image is exactly 1024×1024 and uses RGB or RGBA mode.

- [x] **Step 4: Convert the PNG to a multi-size ICO**

Run with the bundled workspace Python:

```powershell
& 'C:\Users\19213\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "from PIL import Image; from pathlib import Path; p=Path(r'src-tauri/icons/icon.png'); out=Path(r'src-tauri/icons/icon.ico'); image=Image.open(p).convert('RGBA'); image.save(out, format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
```

- [x] **Step 5: Verify both image assets**

Run:

```powershell
& 'C:\Users\19213\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -c "from PIL import Image; png=Image.open(r'src-tauri/icons/icon.png'); ico=Image.open(r'src-tauri/icons/icon.ico'); print('png', png.size, png.mode); print('ico', sorted(ico.ico.sizes()))"
```

Expected:

```text
png (1024, 1024) RGB
ico [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
```

`RGBA` is also valid for the PNG mode.

- [x] **Step 6: Run the offline Rust tests**

Initialize `VsDevCmd.bat` for x64, put the standalone Rust 1.97 bin directory first in `PATH`, and run:

```text
cargo test --manifest-path src-tauri/Cargo.toml --offline
```

Expected: `tauri-build` proceeds past icon validation and all Rust tests pass. Any new compile or test failure must be handled as a separate evidence-based defect.

- [x] **Step 7: Commit**

```powershell
git add src-tauri/icons/icon.png src-tauri/icons/icon.ico docs/superpowers/plans/2026-07-30-ai-art-agent-icon.md
git commit -m "feat: add desktop application icon"
```
