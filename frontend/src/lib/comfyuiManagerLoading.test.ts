// @vitest-environment happy-dom

import { afterEach, beforeAll, expect, test, vi } from "vitest"

type ManagerLoadingWindow = Window & {
  __installComfyuiManagerLoading: () => void
}

beforeAll(async () => {
  await import("./comfyuiManagerLoading.js")
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
  document.getElementById("ai-art-agent-manager-loading")?.remove()
  document.body.replaceChildren()
})

test("HTML 根节点尚未创建时等待 DOMContentLoaded 再挂载", () => {
  const body = document.body
  const documentElement = document.documentElement
  let parsed = false
  vi.spyOn(document, "body", "get").mockImplementation(() => parsed ? body : null)
  vi.spyOn(document, "documentElement", "get").mockImplementation(
    () => parsed ? documentElement : null,
  )

  expect(() => {
    ;(window as ManagerLoadingWindow).__installComfyuiManagerLoading()
  }).not.toThrow()
  expect(document.getElementById("ai-art-agent-manager-loading")).toBeNull()

  parsed = true
  document.dispatchEvent(new Event("DOMContentLoaded"))

  expect(document.getElementById("ai-art-agent-manager-loading")).not.toBeNull()
})

test("ComfyUI 页面就绪前显示加载状态，就绪后自动移除", async () => {
  ;(window as ManagerLoadingWindow).__installComfyuiManagerLoading()

  expect(document.body.textContent).toContain("ComfyUI 模型库正在加载")

  const main = document.createElement("main")
  main.append(document.createElement("button"))
  document.body.append(main)
  await vi.waitFor(() => {
    expect(document.getElementById("ai-art-agent-manager-loading")).toBeNull()
  })
})

test("关键资源加载失败时显示中文错误和重新加载按钮", () => {
  ;(window as ManagerLoadingWindow).__installComfyuiManagerLoading()
  const script = document.createElement("script")
  document.body.append(script)

  script.dispatchEvent(new Event("error"))

  expect(document.body.textContent).toContain("ComfyUI 模型库加载失败")
  expect(document.querySelector("#ai-art-agent-manager-loading style")).not.toBeNull()
  expect(document.querySelector("button")?.textContent).toBe("重新加载")
})

test("页面长时间未就绪时显示超时错误", async () => {
  vi.useFakeTimers()
  ;(window as ManagerLoadingWindow).__installComfyuiManagerLoading()

  await vi.advanceTimersByTimeAsync(30_000)

  expect(document.body.textContent).toContain("ComfyUI 模型库加载超时")
})
