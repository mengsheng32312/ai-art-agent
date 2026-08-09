# ComfyUI Manager 内部窗口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在模型管理顶部提供 Manager 状态和入口，并在软件内部独立窗口中加载完整 ComfyUI 原界面。

**Architecture:** Rust/Tauri 负责创建、复用和重建指向 ComfyUI URL 的子 WebviewWindow；前端桌面适配层统一封装桌面调用和 Web 端新标签页回退；模型管理页负责入口展示，主应用负责打开窗口和重新获得焦点后的模型刷新。

**Tech Stack:** Rust、Tauri 2、Vue 3、TypeScript、Ant Design Vue、Cargo test、Vitest

## Global Constraints

- Manager 入口位于模型管理顶部，不再藏在“远程模型”分类。
- 内部窗口加载完整 ComfyUI 原界面，不复制或注入 Manager 内部组件。
- 同一时间只允许一个 Manager 窗口；重复点击聚焦，地址变化时重建。
- 下载由 ComfyUI Manager 执行，本软件不要求用户逐个选择保存目录。
- Web 端回退为新的浏览器标签页。
- 只验证本次涉及模块，不执行完整回归、重新打包或重新安装。

---

### Task 1: Tauri ComfyUI 内部窗口

**Files:**
- Modify: `src-tauri/src/lib.rs`
- Modify: `src-tauri/tests/desktop.rs`

**Interfaces:**
- Produces: `validate_comfyui_web_url(raw: &str) -> Result<tauri::Url, String>`
- Produces: Tauri command `open_comfyui_manager(url: String) -> Result<(), String>`
- Consumes: 当前配置的 ComfyUI HTTP/HTTPS 地址

- [ ] **Step 1: 写入 URL 校验失败测试**

```rust
#[test]
fn accepts_http_comfyui_urls_and_rejects_other_schemes() {
    assert_eq!(
        validate_comfyui_web_url("http://127.0.0.1:8188").unwrap().as_str(),
        "http://127.0.0.1:8188/"
    );
    assert!(validate_comfyui_web_url("file:///tmp/index.html").is_err());
}
```

- [ ] **Step 2: 运行测试并确认失败**

把测试加入 `src-tauri/src/lib.rs` 现有的 `tests` 模块。

Run: `cd src-tauri && cargo test --lib accepts_http_comfyui_urls_and_rejects_other_schemes`

Expected: FAIL，提示 `validate_comfyui_web_url` 不存在。

- [ ] **Step 3: 实现 URL 校验与窗口命令**

```rust
pub fn validate_comfyui_web_url(raw: &str) -> Result<tauri::Url, String> {
    let url = raw.trim().parse::<tauri::Url>().map_err(|_| "ComfyUI 地址无效".to_string())?;
    if !matches!(url.scheme(), "http" | "https") {
        return Err("ComfyUI 地址只支持 http 或 https".into());
    }
    Ok(url)
}
```

命令使用固定标签 `comfyui-manager`。已存在窗口且 URL 相同时调用 `show` 和 `set_focus`；URL 不同时关闭旧窗口并通过 `tauri::WebviewWindowBuilder` 创建宽 1280、高 820 的新窗口，标题为“ComfyUI 模型库”。把命令加入 `invoke_handler`。同时把 `src-tauri/tests/desktop.rs` 中两个 ComfyUI 启动参数期望补上现有的 `--enable-manager`，使测试与当前启动实现一致。

- [ ] **Step 4: 运行 Tauri 相关测试**

Run: `cd src-tauri && cargo test --lib`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add src-tauri/src/lib.rs src-tauri/tests/desktop.rs
git commit -m "feat: open comfyui in manager window"
```

### Task 2: 前端桌面适配层

**Files:**
- Modify: `frontend/src/lib/desktop.ts`
- Modify: `frontend/src/lib/desktop.test.ts`

**Interfaces:**
- Consumes: Tauri command `open_comfyui_manager`
- Produces: `openComfyuiManager(url: string): Promise<void>`

- [ ] **Step 1: 写入桌面与 Web 回退失败测试**

```ts
test("opens ComfyUI through the desktop command", async () => {
  const invoke = vi.fn().mockResolvedValue(undefined)
  window.__TAURI__ = { core: { invoke } }
  await openComfyuiManager("http://127.0.0.1:8188")
  expect(invoke).toHaveBeenCalledWith("open_comfyui_manager", {
    url: "http://127.0.0.1:8188",
  })
})

test("opens ComfyUI in a browser tab outside Tauri", async () => {
  const open = vi.fn()
  vi.stubGlobal("open", open)
  await openComfyuiManager("http://127.0.0.1:8188")
  expect(open).toHaveBeenCalledWith("http://127.0.0.1:8188", "_blank", "noopener")
})
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm.cmd test -- --run src/lib/desktop.test.ts`

Expected: FAIL，提示 `openComfyuiManager` 不存在。

- [ ] **Step 3: 实现统一打开函数**

```ts
export async function openComfyuiManager(url: string): Promise<void> {
  const tauri = core()
  if (tauri) {
    await tauri.invoke<void>("open_comfyui_manager", { url })
    return
  }
  window.open(url, "_blank", "noopener")
}
```

- [ ] **Step 4: 运行适配层测试**

Run: `cd frontend && npm.cmd test -- --run src/lib/desktop.test.ts`

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add frontend/src/lib/desktop.ts frontend/src/lib/desktop.test.ts
git commit -m "feat: add comfyui manager opener"
```

### Task 3: 顶部 Manager 入口与刷新同步

**Files:**
- Modify: `frontend/src/views/ModelsView.vue`
- Modify: `frontend/src/views/ModelsView.test.ts`
- Modify: `frontend/src/App.vue`
- Modify: `frontend/src/App.test.ts`

**Interfaces:**
- Consumes: `openComfyuiManager(config.api_url)`
- Produces: `ModelsView` 事件 `openManager: []`
- Produces: 主窗口焦点恢复后的 `refreshModels()` 调用

- [ ] **Step 1: 写入顶部入口失败测试**

在 `ModelsView.test.ts` 验证：本地 Manager 不可用时顶部存在“一键启用 Manager”；Manager 可用且已连接时顶部存在“打开 ComfyUI 模型库”，点击后发出 `openManager`；远程模型分类内不再包含启用按钮。

- [ ] **Step 2: 运行测试并确认失败**

Run: `cd frontend && npm.cmd test -- --run src/views/ModelsView.test.ts`

Expected: FAIL，顶部入口或 `openManager` 事件不存在。

- [ ] **Step 3: 实现 ModelsView 顶部入口**

在现有 `model-toolbar-content` 中增加 Manager 状态 `Tag` 和条件按钮；把远程模型页 Alert 的 action 删除。扩展事件定义：

```ts
const emit = defineEmits<{
  openManager: []
  enableManager: []
  // 保留现有事件
}>()
```

- [ ] **Step 4: 写入 App 打开与聚焦刷新失败测试**

在 `App.test.ts` mock `openComfyuiManager` 和 `api.models`，验证 `openManager()` 在连接且 Manager 可用时传入当前 `config.api_url`；当页面为模型管理且 Manager 可用时触发 `window.focus` 会调用模型目录接口。

- [ ] **Step 5: 实现 App 处理逻辑**

增加 `openManager()`：未连接或 Manager 不可用时给出中文提示，否则调用桌面适配层。通过 `onMounted`/`onUnmounted` 注册和清理 `window.focus` 监听器；仅当当前页面为模型管理、连接正常且 Manager 可用时调用 `refreshModels()`。模板为 `ModelsView` 绑定 `@open-manager="openManager"`。

- [ ] **Step 6: 运行前端相关测试和编译**

Run: `cd frontend && npm.cmd test -- --run src/lib/desktop.test.ts src/views/ModelsView.test.ts src/App.test.ts`

Run: `cd frontend && npm.cmd run build`

Expected: 全部 PASS。

- [ ] **Step 7: 提交并推送**

```powershell
git add frontend/src/views/ModelsView.vue frontend/src/views/ModelsView.test.ts frontend/src/App.vue frontend/src/App.test.ts
git commit -m "feat: expose comfyui manager at model toolbar"
git push origin codex/complete-mvp
```

### Task 4: 重启项目

**Files:**
- No file changes.

**Interfaces:**
- Consumes: `D:\Project\ai-art-agent\启动项目.bat`
- Produces: 加载最新代码的桌面开发实例

- [ ] **Step 1: 停止当前项目进程**

只停止命令行或可执行路径属于 `D:\Project\ai-art-agent\.worktrees\complete-mvp` 的前端、后端、桌面和受管 ComfyUI 进程，保留 Codex 自身进程。

- [ ] **Step 2: 运行桌面接口测试**

停止开发进程释放 `src-tauri/target/debug/ai-art-agent.exe` 后执行：

Run: `cd src-tauri && cargo test --test desktop`

Expected: PASS。

- [ ] **Step 3: 重新启动**

Run: `Start-Process -FilePath "D:\Project\ai-art-agent\启动项目.bat" -WorkingDirectory "D:\Project\ai-art-agent" -WindowStyle Minimized`

- [ ] **Step 4: 验证服务**

确认 `http://127.0.0.1:1420/` 返回 200，`http://127.0.0.1:8000/api/health` 返回 `status: ok`。
