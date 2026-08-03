import type { GenerationRequest, GenerationTask } from "../lib/api"

export function createDefaultGenerationRequest(): GenerationRequest {
  return {
    prompt: "",
    negative_prompt: "",
    checkpoint: "",
    width: 1024,
    height: 1024,
    steps: 25,
    cfg: 7,
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
  return connected && Boolean(request.prompt.trim()) && Boolean(request.checkpoint) && !busy
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
