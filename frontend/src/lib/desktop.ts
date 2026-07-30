type TauriCore = {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>
}

type TauriWindow = Window & {
  __TAURI__?: {
    core: TauriCore
  }
}

type AgentEndpoint = {
  pid: number
  port: number
  baseUrl: string
}

let desktopStartupError: string | null = null
let desktopAgentBase: string | null = null

function core(): TauriCore | null {
  return (window as TauriWindow).__TAURI__?.core ?? null
}

export function isDesktop(): boolean {
  return core() !== null
}

export function agentApiBase(): string {
  return isDesktop() && desktopAgentBase
    ? `${desktopAgentBase}/api`
    : "/api"
}

export async function selectComfyuiDirectory(): Promise<string | null> {
  const tauri = core()
  if (!tauri) return null
  return tauri.invoke<string | null>("select_comfyui_directory")
}

export async function startDesktopAgent(): Promise<void> {
  const tauri = core()
  if (!tauri) return
  const endpoint = await tauri.invoke<AgentEndpoint>("start_local_agent")
  desktopAgentBase = endpoint.baseUrl
}

export async function prepareDesktopAgent(): Promise<void> {
  if (!isDesktop()) return
  await startDesktopAgent()
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const response = await fetch(`${agentApiBase()}/health`)
      if (response.ok) {
        const health: unknown = await response.json()
        if (
          typeof health === "object" &&
          health !== null &&
          "status" in health &&
          health.status === "ok" &&
          "service" in health &&
          health.service === "ai-art-agent" &&
          "version" in health &&
          health.version === "0.1.0"
        ) {
          return
        }
      }
    } catch {
      // The packaged process can take a moment to unpack and bind its port.
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  throw new Error("本地 Agent 启动超时")
}

export function recordDesktopStartupError(error: unknown): void {
  desktopStartupError = error instanceof Error ? error.message : String(error)
}

export function takeDesktopStartupError(): string | null {
  const error = desktopStartupError
  desktopStartupError = null
  return error
}

export async function startComfyui(path: string): Promise<void> {
  const tauri = core()
  if (!tauri) return
  await tauri.invoke<number>("start_comfyui", { path })
}

export async function stopComfyui(): Promise<void> {
  const tauri = core()
  if (!tauri) return
  await tauri.invoke<void>("stop_comfyui")
}
