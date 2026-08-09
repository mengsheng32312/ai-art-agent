// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { afterEach, expect, test, vi } from "vitest"

import ComfyuiManagerWindow from "./ComfyuiManagerWindow.vue"

afterEach(() => {
  vi.useRealTimers()
})

test("模型库页面加载完成前立即显示加载状态", async () => {
  const wrapper = mount(ComfyuiManagerWindow, {
    props: { url: "http://127.0.0.1:8188/" },
  })

  expect(wrapper.text()).toContain("ComfyUI 模型库正在加载")
  expect(wrapper.get("iframe").attributes("src")).toBe("http://127.0.0.1:8188/")

  await wrapper.get("iframe").trigger("load")

  expect(wrapper.text()).not.toContain("ComfyUI 模型库正在加载")
  expect(wrapper.get("iframe").classes()).toContain("is-ready")
})

test("模型库长时间未完成加载时显示超时提示", async () => {
  vi.useFakeTimers()
  const wrapper = mount(ComfyuiManagerWindow, {
    props: { url: "http://127.0.0.1:8188/" },
  })

  await vi.advanceTimersByTimeAsync(30_000)

  expect(wrapper.text()).toContain("ComfyUI 模型库加载超时")
  expect(wrapper.get("button").text()).toBe("重新加载")
})
