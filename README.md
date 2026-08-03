# AI Art Agent

AI Art Agent 是面向 ComfyUI 的 Windows 桌面创作界面。用户通过表单选择模型、填写提示词和采样参数；应用负责构建并提交内置工作流、轮询任务状态以及保存生成历史，无需操作 ComfyUI 节点。

## 当前状态

文字生图 MVP 已于 2026-07-30 完成端到端验证：

- 后端 14 项测试、前端 12 项测试和前端生产构建通过。
- 4 项 Rust 集成测试通过。
- mocked E2E 已覆盖配置、checkpoint 列表、任务提交、完成状态和历史记录。
- 桌面 smoke 验证通过：release 程序可启动、内置 Agent 健康接口可用，退出桌面程序时会清理托管 Agent。
- MVP 仅发布 NSIS 安装包；已验证静默安装、启动、健康检查、退出清理和卸载。

普通 Windows 用户请使用 NSIS 安装包：

```text
src-tauri/target/release/bundle/nsis/AI Art Agent_0.1.0_x64-setup.exe
```

安装包目前未做代码签名，Windows 可能显示安全提示。正式分发前应配置 Windows 代码签名证书。

## 功能

- 配置本地 ComfyUI 安装目录或远程 ComfyUI API。
- 原生 Windows 目录选择、目录验证和托管进程清理。
- 自动启动桌面内置 FastAPI Agent。
- 本地模式可启动普通或 Windows Portable 版 ComfyUI。
- 检测连接并读取 checkpoint 列表。
- 模型管理页可读取 ComfyUI 当前可用模型，并在 ComfyUI Manager 可用时展示在线模型库。
- 提交文字生图基础参数和高级参数。
- 展示 queued、running、completed、failed 状态和错误。
- 预览结果并持久化生成历史。

## 环境要求

Web 开发需要：

- Python 3.11 或更高版本。
- Node.js 20 或更高版本。

桌面开发和安装包构建还需要：

- Rust stable MSVC 工具链。
- Visual Studio 2022 Build Tools。
- “使用 C++ 的桌面开发”工作负载和 Windows SDK。
- Microsoft Edge WebView2 Runtime。

如果机器上同时存在损坏的 rustup shim 和 standalone Rust，请把可用 Rust 的 `bin` 目录放在 `PATH` 最前，并确认 `cargo --version`、`rustc --version`、`rustdoc --version` 都来自同一目录。运行 Cargo/Tauri 构建前请初始化 Visual Studio x64 开发环境。

## 安装依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test,package]"

cd ..\frontend
npm install
```

## 开发运行

仅运行浏览器版本：

```powershell
.\scripts\dev.ps1
```

随后打开 `http://127.0.0.1:1420`。Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

运行 Tauri 桌面版本：

```powershell
.\scripts\tauri.ps1 dev
```

桌面层会启动本地 Agent；关闭应用时会清理由本应用启动的 Agent 和 ComfyUI 进程。

## 连接 ComfyUI

本地模式：

1. 在“连接设置”中选择包含 `main.py` 的 ComfyUI 目录，或选择 Windows Portable 版的根目录。
2. 保存配置并启动/测试连接。
3. 应用只会管理由自身启动的 ComfyUI 进程，不会关闭用户手动启动的实例。

远程模式：

1. 填写 ComfyUI HTTP API 地址，例如 `http://192.168.1.20:8188`。
2. 保存并测试连接。
3. 应用只访问远程 HTTP API，不访问远程主机文件系统。

连接成功后，在“图片生成”页选择 checkpoint、填写提示词和参数并提交；结果可在当前任务和“历史记录”中查看。

## 模型管理

- 本地模型区读取 ComfyUI 实际可用的 checkpoint、LoRA、VAE 和 ControlNet。
- 在线模型库依赖 ComfyUI Manager；未安装 Manager 时只展示本地模型。
- 本地模式并选择 ComfyUI 目录后，可判断模型文件是否已存在，并提交下载任务。

## 验证

运行后端、前端和当前机器可用的 Rust 检查：

```powershell
.\scripts\verify.ps1
```

也可以分别运行：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests -v
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run build
cargo test --manifest-path src-tauri\Cargo.toml
```

首次运行应允许 Cargo 在线解析和下载依赖。只有确认本机 Cargo 缓存完整后，才可按需追加 `--offline`。

构建内置后端：

```powershell
.\scripts\package-backend.ps1
```

构建 release 桌面程序和 NSIS 安装包：

```powershell
.\scripts\tauri.ps1 build
```

Tauri 会把 NSIS 构建工具缓存到已忽略的 `src-tauri/target/.tauri/`。首次构建需要访问对应工具的官方分发地址；网络较慢时可能需要预先准备该缓存。

## MVP 限制

- 只包含基础文字生图工作流。
- 不恢复应用关闭时仍在运行的生成任务。
- 远程结果继续由远程 ComfyUI 的 `/view` 接口提供。
- NSIS 安装包尚未签名；本轮已在隔离目录完成静默安装、启动和卸载验证。
- 需要用户自行安装、启动并维护 ComfyUI 及其模型。
