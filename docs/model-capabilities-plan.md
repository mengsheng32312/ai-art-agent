# 模型能力补齐计划：参考图 / 参考视频 / LoRA / ControlNet / Hires fix

## 现状

当前两个生成工作流都是纯文本条件：

- 图片：`CheckpointLoaderSimple -> CLIPTextEncode x2 -> EmptyLatentImage -> KSampler -> VAEDecode -> SaveImage`
- 视频：`CheckpointLoaderSimple -> CLIPTextEncode x2 -> ADE_AnimateDiffLoaderGen1 -> EmptyLatentImage -> KSampler -> VAEDecode -> SaveAnimatedWEBP`

模型库已能识别 LoRA、ControlNet、VAE 类型，但生成流程没有对应节点，选不了、用不上。也没有任何输入文件（参考图/参考视频）的上传与落盘链路。

## 目标能力

| 能力 | 页面 | 依赖节点（ComfyUI 本体或默认安装） | 说明 |
| --- | --- | --- | --- |
| 参考图重绘（img2img） | 图片生成 | `LoadImage` + `VAEEncode` | 参考图作为采样起点，denoise 控制保留程度 |
| LoRA 叠加 | 图片 / 视频生成 | `LoraLoader` | 支持最多 3 个 LoRA，各带 model/clip 强度 |
| ControlNet 控制 | 图片生成 | `ControlNetLoader` + 预处理器 + `ControlNetApplyAdvanced` | 线稿/深度/姿态等条件约束 |
| Hires fix | 图片生成 | `LatentUpscale` + 二次 `KSampler` | 先低分辨率采样再放大精修 |
| 图生视频（I2V） | 视频生成 | `WanImageToVideo`（ComfyUI 内置） | 参考图作为视频首帧 |
| 视频生视频（V2V） | 视频生成 | `WanVideoToVideo`（ComfyUI 内置） | 参考视频首尾帧 + 运动描述 |

技术决策：I2V/V2V 使用 ComfyUI 0.3+ 内置的 Wan 节点，不依赖自定义节点；现有 AnimateDiff 文生视频流程保持不变。因此视频生成页需要支持三种模式：文生视频（AnimateDiff）、图生视频（Wan I2V）、视频生视频（Wan V2V）。

## 总设计

### 输入文件上传

- 后端新增 `POST /api/upload`（multipart），按 `kind=image|video` 接收文件。
- 远程模式：转发到 ComfyUI `POST /upload/image` 或 `/upload/video`，返回远端文件名。
- 本地模式：直接写入本地 ComfyUI `input/` 目录，返回文件名与本地路径。
- 前端表单用 antd Upload 上传，成功后显示本地预览缩略图，文件名写入 `GenerationRequest`。

### 工作流扩展（图片）

`reference_image` 存在时：

```
LoadImage -> VAEEncode -> KSampler(latent_image=VAEEncode, denoise=<表单值>)
```

LoRA（`LoraLoader`）插在 CheckpointLoader 之后，KSampler 的 model/clip 与两个 CLIPTextEncode 的 clip 都改接 LoRA 输出。ControlNet（`ControlNetApplyAdvanced`）插在 CLIPTextEncode 之后、KSampler 之前。Hires fix 在第一次 KSampler 后接 `LatentUpscale` 与第二次 KSampler。

### 工作流扩展（视频）

- 文生视频：维持现有 AnimateDiff 链路。
- 图生视频：Wan 模型三件套（`UNETLoader` + `CLIPLoader` + `VAELoader`）→ `CLIPTextEncode` → `WanImageToVideo` → `KSampler` → `VAEDecode` → `SaveAnimatedWEBP`。模型选择需要 Wan 专用 checkpoint（前端模型库按 usage=video 选择）。
- 视频生视频：`WanVideoToVideo`，start/end 帧来自上传视频的首尾帧。

## 分阶段任务

### Phase 1：上传基础设施

- [x] 后端：`ComfyClient.upload_media`（远程转发）、本地落盘、`POST /api/upload`、`UploadResponse` schema
- [x] 前端：`api.uploadFile`、上传控件与预览（控件随 Phase 2 图片页一起落地）
- [x] 验收：本地与远程模式各上传一张图/一段视频，返回文件名；测试通过（10 个相关测试通过）

### Phase 2：参考图重绘（img2img）

- [x] 后端：`GenerationRequest.reference_image`、图片 workflow 增加 `LoadImage + VAEEncode` 分支
- [x] 前端：图片生成页参考图上传 + 说明（denoise 语义），提交透传
- [x] 验收：上传参考图生成，输出保持参考图比例；workflow 与前端测试通过

### Phase 3：LoRA

- [x] 后端：`GenerationRequest.loras`、workflow 插入 `LoraLoader` 链
- [x] 前端：LoRA 选择（最多 3 个）+ model/clip 强度
- [x] 验收：图片与视频生成均可叠加 LoRA（全量 46 个后端测试通过）

另：顺手修复了 `build_*_workflow` 的 `filename_prefix` 优先级问题（显式参数被默认值遮蔽），对应测试一并变绿。

### Phase 4：ControlNet

- [ ] 后端：`GenerationRequest.controlnet`、workflow 插入预处理器 + `ControlNetApplyAdvanced`
- [ ] 前端：ControlNet 开关、模型、预处理类型（Canny/Depth/Lineart/OpenPose）、强度与生效区间
- [ ] 验收：上传条件图并生成，条件约束生效

### Phase 5：Hires fix

- [ ] 后端：`GenerationRequest.hires`、二次采样链
- [ ] 前端：Hires 开关、放大倍率、二次 denoise
- [ ] 验收：开启后输出分辨率放大且细节提升

### Phase 6：图生视频 / 视频生视频

- [ ] 后端：视频三种模式分支、Wan 三件套模型加载、首尾帧提取
- [ ] 前端：视频生成页模式切换（文生视频/图生视频/视频生视频）、参考图/参考视频上传
- [ ] 验收：三种模式均可生成；模型库按 usage 过滤正确

### Phase 7：回归与交付

- [ ] 全量测试 + 前端构建 + 打包回归
- [ ] 更新模型库"应用"逻辑覆盖新能力

## 边界与取舍

- V2V 采用 Wan 首尾帧方案，参考视频提供首尾构图约束，不是逐帧运动迁移。
- ControlNet 预处理器按 `comfyui_controlnet_aux` 常用节点实现，按"默认已安装"处理。
- 图片生成页 checkpoint 过滤 image 用途；视频生成页按模式过滤对应模型。
