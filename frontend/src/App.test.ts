// @vitest-environment happy-dom

import { shallowMount } from "@vue/test-utils"
import { expect, test, vi } from "vitest"

import App from "./App.vue"
import type { Config } from "./lib/api"

const desktopMocks = vi.hoisted(() => ({
  selectDirectory: vi.fn(),
}))
const apiMocks = vi.hoisted(() => ({
  saveConfig: vi.fn(),
}))

vi.mock("./lib/desktop", () => ({
  isDesktop: () => true,
  enableComfyuiManager: vi.fn(),
  openInExplorer: vi.fn(),
  prepareDesktopAgent: vi.fn(() => new Promise(() => {})),
  recordDesktopStartupError: vi.fn(),
  selectComfyuiDirectory: vi.fn(),
  selectDirectory: desktopMocks.selectDirectory,
  startComfyui: vi.fn(),
  takeDesktopStartupError: vi.fn(() => null),
}))

vi.mock("./lib/api", async importOriginal => {
  const original = await importOriginal<typeof import("./lib/api")>()
  return {
    ...original,
    api: {
      ...original.api,
      saveConfig: apiMocks.saveConfig,
    },
  }
})

test("连接设置在后台配置加载前默认使用本地模式", () => {
  const wrapper = shallowMount(App)
  const vm = wrapper.vm as unknown as { config: Config }

  expect(vm.config.mode).toBe("local")
})

test("选择本地模型目录后立即保存设置", async () => {
  desktopMocks.selectDirectory.mockResolvedValue("D:\\ComfyUI\\models")
  apiMocks.saveConfig.mockResolvedValue({})
  const wrapper = shallowMount(App)
  const vm = wrapper.vm as unknown as {
    config: Config
    chooseLocalModelDirectory: () => Promise<void>
  }

  await vm.chooseLocalModelDirectory()

  expect(vm.config.local_model_path).toBe("D:\\ComfyUI\\models")
  expect(apiMocks.saveConfig).toHaveBeenCalledWith(vm.config)
})
