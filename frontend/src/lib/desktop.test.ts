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
  const invoke = vi.fn().mockResolvedValue({
    pid: 42,
    port: 8001,
    baseUrl: "http://127.0.0.1:8001",
  })
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  const fetch = vi
    .fn()
    .mockRejectedValueOnce(new Error("connection refused"))
    .mockResolvedValueOnce(
      new Response(
        '{"status":"ok","service":"ai-art-agent","version":"0.1.0"}',
        { status: 200 },
      ),
    )
  vi.stubGlobal("fetch", fetch)

  const prepare = (desktop as DesktopWithBootstrap).prepareDesktopAgent
  expect(prepare).toBeTypeOf("function")
  const preparing = prepare()
  await vi.advanceTimersByTimeAsync(250)
  await preparing

  expect(invoke).toHaveBeenCalledWith("start_local_agent")
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(fetch).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/health",
  )
})

test("rejects a healthy-looking response from the wrong service", async () => {
  vi.useFakeTimers()
  const invoke = vi.fn().mockResolvedValue({
    pid: 43,
    port: 8002,
    baseUrl: "http://127.0.0.1:8002",
  })
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  const fetch = vi.fn().mockResolvedValue(
    new Response('{"status":"ok","version":"0.1.0"}', { status: 200 }),
  )
  vi.stubGlobal("fetch", fetch)

  const preparation = expect(
    (desktop as DesktopWithBootstrap).prepareDesktopAgent(),
  ).rejects.toThrow()
  await vi.runAllTimersAsync()
  await preparation

  expect(fetch).toHaveBeenCalledTimes(40)
  expect(fetch).toHaveBeenCalledWith(
    "http://127.0.0.1:8002/api/health",
  )
})

test("rejects a health response from an incompatible agent version", async () => {
  vi.useFakeTimers()
  const invoke = vi.fn().mockResolvedValue({
    pid: 44,
    port: 8003,
    baseUrl: "http://127.0.0.1:8003",
  })
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  const fetch = vi.fn().mockResolvedValue(
    new Response(
      '{"status":"ok","service":"ai-art-agent","version":"0.2.0"}',
      { status: 200 },
    ),
  )
  vi.stubGlobal("fetch", fetch)

  const preparation = expect(
    (desktop as DesktopWithBootstrap).prepareDesktopAgent(),
  ).rejects.toThrow()
  await vi.runAllTimersAsync()
  await preparation

  expect(fetch).toHaveBeenCalledTimes(40)
})

test("rejects a health response whose status is not ok", async () => {
  vi.useFakeTimers()
  const invoke = vi.fn().mockResolvedValue({
    pid: 45,
    port: 8004,
    baseUrl: "http://127.0.0.1:8004",
  })
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  const fetch = vi.fn().mockResolvedValue(
    new Response(
      '{"status":"starting","service":"ai-art-agent","version":"0.1.0"}',
      { status: 200 },
    ),
  )
  vi.stubGlobal("fetch", fetch)

  const preparation = expect(
    (desktop as DesktopWithBootstrap).prepareDesktopAgent(),
  ).rejects.toThrow()
  await vi.runAllTimersAsync()
  await preparation

  expect(fetch).toHaveBeenCalledTimes(40)
})

test("uses the development proxy outside Tauri", () => {
  expect(desktop.agentApiBase()).toBe("/api")
})

test("preserves the desktop startup error for the UI once", () => {
  const desktopApi = desktop as DesktopWithBootstrap

  desktopApi.recordDesktopStartupError(new Error("backend missing"))

  expect(desktopApi.takeDesktopStartupError()).toBe("backend missing")
  expect(desktopApi.takeDesktopStartupError()).toBeNull()
})
