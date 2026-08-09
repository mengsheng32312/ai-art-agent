// @vitest-environment happy-dom

import { flushPromises, shallowMount } from "@vue/test-utils"
import { expect, test, vi } from "vitest"

import App from "./App.vue"
import type { Config, ModelCatalogResponse } from "./lib/api"

const desktopMocks = vi.hoisted(() => ({
  openComfyuiManager: vi.fn(),
  selectDirectory: vi.fn(),
}))
const apiMocks = vi.hoisted(() => ({
  models: vi.fn(),
  saveConfig: vi.fn(),
}))

vi.mock("./lib/desktop", () => ({
  isDesktop: () => true,
  enableComfyuiManager: vi.fn(),
  openComfyuiManager: desktopMocks.openComfyuiManager,
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
      models: apiMocks.models,
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

test("通过当前 ComfyUI 地址打开模型库窗口", async () => {
  desktopMocks.openComfyuiManager.mockResolvedValue(undefined)
  const wrapper = shallowMount(App)
  const vm = wrapper.vm as unknown as {
    config: Config
    connected: boolean
    modelCatalog: ModelCatalogResponse
    openManager: () => Promise<void>
  }
  vm.connected = true
  vm.config.api_url = "http://127.0.0.1:8188"
  vm.modelCatalog.manager_available = true

  await vm.openManager()

  expect(desktopMocks.openComfyuiManager).toHaveBeenCalledWith("http://127.0.0.1:8188")
  wrapper.unmount()
})

test("从模型库窗口返回模型页时刷新目录", async () => {
  const catalog: ModelCatalogResponse = {
    connected: true,
    manager_available: true,
    message: "ComfyUI 已连接",
    remote_models: [],
    local_models: [],
    online_models: [],
  }
  apiMocks.models.mockResolvedValue(catalog)
  const wrapper = shallowMount(App)
  const vm = wrapper.vm as unknown as {
    page: string
    connected: boolean
    catalogLoaded: boolean
    modelCatalog: ModelCatalogResponse
  }
  vm.catalogLoaded = true
  vm.page = "models"
  vm.connected = true
  vm.modelCatalog.manager_available = true
  await wrapper.vm.$nextTick()
  apiMocks.models.mockClear()

  window.dispatchEvent(new Event("focus"))
  await flushPromises()

  expect(apiMocks.models).toHaveBeenCalled()
  wrapper.unmount()
})
