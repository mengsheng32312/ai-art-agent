# AI Art Agent

一个面向 ComfyUI 的简化创作界面。用户填写提示词和常用参数，应用负责构造并提交 ComfyUI 工作流。

## 当前功能

- 本地或远程 ComfyUI API 配置
- 连接检测与 checkpoint 列表
- 文生图参数表单
- 任务提交、状态轮询和结果预览
- 本地历史记录

## 开发运行

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:1420`。前端会将 `/api` 请求代理到 `http://127.0.0.1:8000`。

## 使用

进入“连接设置”，选择本地或远程模式，填写 ComfyUI API 地址并保存。连接成功后回到“图片生成”，选择 checkpoint、填写画面描述并提交。

本地目录选择和自动启动 ComfyUI 需要 Tauri 桌面层；当前机器未安装 Rust，因此该部分尚未编译。
