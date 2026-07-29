# AI Art Agent

AI Art Agent 是面向 ComfyUI 的 Windows 桌面创作界面。用户通过表单选择模型、填写提示词和采样参数；应用负责构建并提交内置工作流、轮询任务状态以及保存生成历史，不需要操作 ComfyUI 节点。

## 项目状态

**进行中**

截至 2026-07-29：

- 后端功能与测试已补齐，14 项测试通过。
- 前端设置、生成、历史和错误恢复流程已补齐，12 项测试通过，生产构建通过。
- 已使用本机 ComfyUI 完成真实文生图联调，模型读取、任务提交、结果展示和历史保存均通过。
- PyInstaller 单文件 Agent 已完成构建与进程冒烟验证。
- Tauri 2 桌面源码、进程管理、资源和 MSI/NSIS 配置已补齐。
- 当前待完成：首次 Cargo 依赖下载、Rust 单元测试、Tauri 桌面编译及安装包验证。

## 当前功能

- 本地 ComfyUI 安装目录或远程 ComfyUI API 配置
- 原生 Windows 目录选择、目录验证和托管进程清理
- 自动启动桌面内置 FastAPI Agent
- 本地模式自动启动普通或 Windows Portable 版 ComfyUI
- 连接检测与 checkpoint 列表
- 文生图基础及高级参数
- queued、running、completed、failed 状态与错误展示
- 结果预览和持久化历史缩略图
- PyInstaller 单文件后端与 Tauri 2 的 MSI/NSIS 打包配置

## 环境要求

Web 开发需要：

- Python 3.11 或更高版本
- Node.js 20 或更高版本

桌面开发和安装包构建还需要：

- Rust stable（通过 rustup 或官方独立安装包安装）
- Visual Studio 2022 Build Tools
- “使用 C++ 的桌面开发”工作负载及 Windows SDK
- Microsoft Edge WebView2 Runtime

Windows 10 和 Windows 11 通常已包含 WebView2。Tauri 构建会使用系统的 MSVC 和 Windows SDK。

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

桌面层会启动本地 Agent；关闭应用时会清理由应用托管的 Agent 和 ComfyUI 进程。

## 使用方式

1. 打开“连接设置”。
2. 本地模式下选择包含 `main.py` 的 ComfyUI 目录，或选择 Windows Portable 根目录；远程模式下填写 API 地址。
3. 保存并测试连接。
4. 返回“图片生成”，选择 checkpoint、填写提示词和参数后提交。
5. 在当前结果区查看进度、错误和图片，或到“历史记录”查看已保存任务。

远程模式只访问 ComfyUI HTTP API，不访问远程主机文件系统。

## 验证

运行当前机器能够支持的全部检查：

```powershell
.\scripts\verify.ps1
```

该脚本运行后端测试、前端组件测试、TypeScript 检查和生产构建；检测到 Cargo 时还会运行 Rust 单元测试。没有 Rust/MSVC 的机器会明确跳过桌面编译步骤。

单独构建并冒烟验证内置后端：

```powershell
.\scripts\package-backend.ps1
.\backend\dist\ai-art-agent-backend.exe
```

构建 Windows 安装包：

```powershell
.\scripts\tauri.ps1 build
```

Tauri 的构建钩子会先生成 `backend\dist\ai-art-agent-backend.exe`，再构建前端并生成 MSI、NSIS 安装包。

## MVP 限制

- 不下载或管理模型、LoRA。
- 只包含基础文生图工作流。
- 不恢复应用关闭时仍在运行的生成任务。
- 远程结果继续由远程 ComfyUI 的 `/view` 接口提供。
- Windows 安装包默认未签名；正式分发前应配置代码签名。
