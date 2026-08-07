import type { GenerationRequest, GenerationTask } from "../lib/api"

export function createDefaultGenerationRequest(): GenerationRequest {
  return {
    prompt: "",
    negative_prompt: "",
    checkpoint: "",
    media_type: "image",
    video_mode: "t2v",
    vae: "",
    reference_image: "",
    reference_video: "",
    loras: [],
    controlnet: null,
    hires: null,
    frames: 16,
    motion_model: "",
    beta_schedule: "sqrt_linear (AnimateDiff)",
    fps: 8,
    quality: 80,
    lossless: false,
    method: "default",
    output_prefix: "AIArtAgent",
    width: 512,
    height: 512,
    steps: 25,
    cfg: 7,
    denoise: 1,
    seed: -1,
    sampler: "euler",
    scheduler: "normal",
    batch_size: 1,
  }
}

export function canSubmitGeneration(
  request: GenerationRequest,
  connected: boolean,
  busy: boolean,
): boolean {
  const motionOk =
    request.media_type !== "video" ||
    request.video_mode !== "t2v" ||
    Boolean(request.motion_model?.trim())
  const mediaOk =
    request.media_type !== "video" ||
    request.video_mode !== "i2v" ||
    Boolean(request.reference_image?.trim())
  const videoOk =
    request.media_type !== "video" ||
    request.video_mode !== "v2v" ||
    Boolean(request.reference_video?.trim())
  return (
    connected &&
    Boolean(request.prompt.trim()) &&
    Boolean(request.checkpoint) &&
    motionOk &&
    mediaOk &&
    videoOk &&
    !busy
  )
}

// 返回生成按钮不可用的首要原因，用于表单和预览区同步反馈。
export function getGenerationBlockedReason(
  request: GenerationRequest,
  connected: boolean,
  busy: boolean,
  checkpoints: string[],
): string {
  if (busy) return "正在生成，请稍候"
  if (!connected) return "请先在连接设置中完成 ComfyUI 连接"
  if (!request.prompt.trim()) return "请输入画面描述"
  if (request.media_type === "video" && request.video_mode === "t2v" && !request.motion_model?.trim())
    return "请选择运动模型"
  if (request.media_type === "video" && request.video_mode === "i2v" && !request.reference_image?.trim())
    return "请上传参考图"
  if (request.media_type === "video" && request.video_mode === "v2v" && !request.reference_video?.trim())
    return "请上传参考视频"
  if (!checkpoints.length) return "当前没有可用模型，请检查 ComfyUI 模型目录"
  if (!request.checkpoint) return "请选择模型"
  return ""
}

export function upsertTask(tasks: GenerationTask[], task: GenerationTask): GenerationTask[] {
  const index = tasks.findIndex(item => item.id === task.id)
  if (index === -1) return [task, ...tasks]

  const next = [...tasks]
  next[index] = task
  return next
}
