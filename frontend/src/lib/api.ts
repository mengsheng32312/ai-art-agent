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
  width: number
  height: number
  steps: number
  cfg: number
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${agentApiBase()}${path}`, {
      headers: { "Content-Type": "application/json" },
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
    request<ConnectionStatus>("/comfy/status", {
      method: "POST",
      body: JSON.stringify(config),
    }),
  checkpoints: () => request<string[]>("/comfy/checkpoints"),
  generate: (data: GenerationRequest) =>
    request<GenerationTask>("/generations", { method: "POST", body: JSON.stringify(data) }),
  generation: (id: string) => request<GenerationTask>(`/generations/${id}`),
  history: () => request<GenerationTask[]>("/history"),
}
