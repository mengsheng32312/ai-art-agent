// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test } from "vitest"

import ModelsView from "./ModelsView.vue"

test("本地连接把接口返回的模型标记为 ComfyUI 可用模型", () => {
  const wrapper = mount(ModelsView, {
    props: {
      config: {
        mode: "local",
        comfyui_path: "D:\\ComfyUI",
        local_model_path: null,
        api_url: "http://127.0.0.1:8188",
      },
      connected: true,
      catalog: {
        connected: true,
        manager_available: false,
        message: "ComfyUI 已连接",
        remote_models: [],
        local_models: [],
        online_models: [],
      },
      catalogLoaded: true,
      loading: false,
      downloadingKey: "",
      downloadingModels: [],
      enablingManager: false,
    },
  })

  expect(wrapper.text()).toContain("ComfyUI 可用模型")
  expect(wrapper.text()).not.toContain("远程可用模型")
})

test("本地 Manager 不可用时提供一键启用按钮", async () => {
  const wrapper = mount(ModelsView, {
    props: {
      config: {
        mode: "local",
        comfyui_path: "D:\\ComfyUI",
        local_model_path: "D:\\ComfyUI\\models",
        api_url: "http://127.0.0.1:8188",
      },
      connected: true,
      catalog: {
        connected: true,
        manager_available: false,
        message: "ComfyUI 已连接",
        remote_models: [],
        local_models: [],
        online_models: [],
      },
      catalogLoaded: true,
      loading: false,
      downloadingKey: "",
      downloadingModels: [],
      enablingManager: false,
    },
  })

  const button = wrapper.findAll("button").find(item => item.text().includes("一键启用 Manager"))
  expect(button).toBeDefined()
  await button?.trigger("click")
  expect(wrapper.emitted("enableManager")).toHaveLength(1)
})
