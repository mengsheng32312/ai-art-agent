// @vitest-environment happy-dom

import { shallowMount } from "@vue/test-utils"
import { expect, test, vi } from "vitest"

import App from "./App.vue"
import type { Config } from "./lib/api"

vi.mock("./lib/desktop", () => ({
  isDesktop: () => false,
  openInExplorer: vi.fn(),
  prepareDesktopAgent: vi.fn(() => new Promise(() => {})),
  recordDesktopStartupError: vi.fn(),
  selectComfyuiDirectory: vi.fn(),
  selectDirectory: vi.fn(),
  startComfyui: vi.fn(),
  takeDesktopStartupError: vi.fn(() => null),
}))

test("连接设置在后台配置加载前默认使用本地模式", () => {
  const wrapper = shallowMount(App)
  const vm = wrapper.vm as unknown as { config: Config }

  expect(vm.config.mode).toBe("local")
})
