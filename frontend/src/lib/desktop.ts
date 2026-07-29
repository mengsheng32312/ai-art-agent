type TauriCore = {
  invoke<T>(command: string, args?: Record<string, unknown>): Promise<T>
}

type TauriWindow = Window & {
  __TAURI__?: {
    core: TauriCore
  }
}

let desktopStartupError: string | null = null

function core(): TauriCore | null {
  return (window as TauriWindow).__TAURI__?.core ?? null
}

export function isDesktop(): boolean {
  return core() !== null
}

export function agentApiBase(): string {
  return isDesktop() ? "http://127.0.0.1:8000/api" : "/api"
}

export async function selectComfyuiDirectory(): Promise<string | null> {
  const tauri = core()
  if (!tauri) return null
  return tauri.invoke<string | null>("select_comfyui_directory")
}

export async function startDesktopAgent(): Promise<void> {
  const tauri = core()
  if (!tauri) return
  await tauri.invoke<number>("start_local_agent")
}

export async function prepareDesktopAgent(): Promise<void> {
  if (!isDesktop()) return
  await startDesktopAgent()
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const response = await fetch(`${agentApiBase()}/health`)
      if (response.ok) return
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
