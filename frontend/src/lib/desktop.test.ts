import { afterEach, expect, test, vi } from "vitest"

import * as desktop from "./desktop"

type DesktopWithBootstrap = typeof desktop & {
  prepareDesktopAgent: () => Promise<void>
  recordDesktopStartupError: (error: unknown) => void
  takeDesktopStartupError: () => string | null
}

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  delete (window as Window & { __TAURI__?: unknown }).__TAURI__
})

test("waits for the packaged agent to become healthy", async () => {
  vi.useFakeTimers()
  const invoke = vi.fn().mockResolvedValue(42)
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error("connection refused"))
    .mockResolvedValueOnce(new Response('{"status":"ok"}', { status: 200 }))
  vi.stubGlobal("fetch", fetch)

  const prepare = (desktop as DesktopWithBootstrap).prepareDesktopAgent
  expect(prepare).toBeTypeOf("function")
  const preparing = prepare()
  await vi.advanceTimersByTimeAsync(250)
  await preparing

  expect(invoke).toHaveBeenCalledWith("start_local_agent")
  expect(fetch).toHaveBeenCalledTimes(2)
})

test("preserves the desktop startup error for the UI once", () => {
  const desktopApi = desktop as DesktopWithBootstrap

  desktopApi.recordDesktopStartupError(new Error("backend missing"))

  expect(desktopApi.takeDesktopStartupError()).toBe("backend missing")
  expect(desktopApi.takeDesktopStartupError()).toBeNull()
})
