import { agentApiBase } from "./desktop"

export type Config = {
  mode: "local" | "remote"
  comfyui_path: string | null
  api_url: string
}

export type ConnectionStatus = {
  connected: boolean
  message: string
}

export type GenerationRequest = {
  prompt: string
  negative_prompt: string
  checkpoint: string
  media_type: "image" | "video"
  vae: string
  frames: number
  motion_model: string
  beta_schedule: string
  fps: number
  quality: number
  lossless: boolean
  method: string
  output_prefix: string
  width: number
  height: number
  steps: number
  cfg: number
  denoise: number
  seed: number
  sampler: string
  scheduler: string
  batch_size: number
}

export type GenerationTask = {
  id: string
  status: "queued" | "running" | "completed" | "failed"
  progress: number
  request: GenerationRequest
  prompt_id: string | null
  outputs: string[]
  error: string | null
}

export type ModelItem = {
  id: string
  name: string
  kind: "checkpoint" | "lora" | "controlnet" | "vae" | "other"
  usage: "image" | "video"
  filename: string
  source: "comfyui" | "local" | "manager"
  installed: boolean
  path: string | null
  description: string
  preview_url: string | null
  size_label: string | null
  reference_url: string | null
}

export type ModelCatalogResponse = {
  connected: boolean
  manager_available: boolean
  message: string
  remote_models: ModelItem[]
  local_models: ModelItem[]
  online_models: ModelItem[]
}

export type ManagerQueueStatus = {
  total_count: number
  done_count: number
  in_progress_count: number
  is_processing: boolean
}

export type UploadResponse = {
  name: string
  path: string | null
  mode: "local" | "remote"
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    const headers: Record<string, string> = init?.body instanceof FormData
      ? {}
      : { "Content-Type": "application/json" }
    response = await fetch(`${agentApiBase()}${path}`, {
      headers,
      ...init,
    })
  } catch {
    throw new Error("软件后台未连接，请重启应用或稍后再试")
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? `请求失败 (${response.status})`)
  }
  return response.json()
}

export const api = {
  config: () => request<Config>("/config"),
  saveConfig: (config: Config) =>
    request<Config>("/config", { method: "PUT", body: JSON.stringify(config) }),
  status: () => request<ConnectionStatus>("/comfy/status"),
  checkStatus: (config: Config) =>
    request<ConnectionStatus>("/comfy/status", { method: "POST", body: JSON.stringify(config) }),
  checkpoints: () => request<string[]>("/comfy/checkpoints"),
  videoModels: () => request<string[]>("/comfy/video-models"),
  vaeModels: () => request<string[]>("/comfy/vae-models"),
  generate: (data: GenerationRequest) =>
    request<GenerationTask>("/generations", { method: "POST", body: JSON.stringify(data) }),
  generation: (id: string) => request<GenerationTask>(`/generations/${id}`),
  history: () => request<GenerationTask[]>("/history"),
  deleteHistory: (id: string) =>
    request<{ ok: boolean }>(`/history/${id}`, { method: "DELETE" }),
  models: () => request<ModelCatalogResponse>("/models/catalog"),
  managerStatus: () => request<ManagerQueueStatus>("/models/manager/status"),
  uploadFile: (file: File, kind: "image" | "video") => {
    const form = new FormData()
    form.append("file", file)
    return request<UploadResponse>(`/upload?kind=${kind}`, {
      method: "POST",
      body: form,
    })
  },
  downloadModel: (model_id: string, destination: "remote" | "local" = "local") =>
    request<ModelItem>("/models/download", {
      method: "POST",
      body: JSON.stringify({ model_id, destination }),
    }),
}

/** 把远程 ComfyUI 图片地址转换为本地后端代理地址，避免浏览器直连隧道不稳定。 */
export function proxiedImageUrl(url: string | null): string {
  if (!url) return ""
  if (url.startsWith("local:")) {
    return `${agentApiBase()}/comfy/local-model-image?path=${encodeURIComponent(url.slice(6))}`
  }
  try {
    const parsed = new URL(url)
    if (!/^https?:$/.test(parsed.protocol)) return url
    const query = new URLSearchParams(parsed.searchParams)
    if (!query.get("filename")) return url
    return `${agentApiBase()}/comfy/view?${query.toString()}`
  } catch {
    return url
  }
}

export type SaveLocation = {
  kind: "path" | "url"
  label: string
  text: string
}

/** 解析生成结果的本地保存位置或远程地址，用于历史记录“查看位置”。 */
export function resolveSaveLocation(
  task: GenerationTask,
  config: Config,
): SaveLocation | null {
  const url = task.outputs[0]
  if (!url) return null
  try {
    const parsed = new URL(url)
    const filename = parsed.searchParams.get("filename")
    if (!filename) return { kind: "url", label: "结果地址", text: url }
    const subfolder = parsed.searchParams.get("subfolder") ?? ""
    if (config.mode === "local" && config.comfyui_path) {
      const parts = [config.comfyui_path, "output", subfolder, filename].filter(Boolean)
      return { kind: "path", label: "本地保存位置", text: parts.join("\\") }
    }
    return { kind: "url", label: "远程图片地址", text: url }
  } catch {
    return { kind: "url", label: "结果地址", text: url }
  }
}
