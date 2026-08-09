// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test } from "vitest"

import ModelsView from "./ModelsView.vue"

const capabilityModel = {
  id: "model-1",
  name: "基础模型",
  kind: "checkpoint" as const,
  usage: "image" as const,
  filename: "model.safetensors",
  source: "comfyui" as const,
  installed: true,
  path: null,
  description: "model",
  preview_url: null,
  size_label: null,
  reference_url: null,
  capability_profile: {
    capabilities: ["text_to_image" as const],
    required_inputs: {},
    required_components: {},
    workflow_family: { text_to_image: "standard_checkpoint" },
    description_zh: "通用图片模型",
    recommended_params: {},
    confirmed: true,
  },
}

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

test("模型能力设置可以保存用户确认的用途", async () => {
  const wrapper = mount(ModelsView, {
    attachTo: document.body,
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
        remote_models: [capabilityModel],
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

  const settings = wrapper.findAll("button").find(item => item.text().includes("能力设置"))
  await settings?.trigger("click")
  const save = document.body.querySelector<HTMLElement>('[data-testid="save-capabilities"]')
  save?.click()
  await wrapper.vm.$nextTick()

  expect(wrapper.emitted("saveCapabilities")?.[0]?.[0]).toMatchObject({
    filename: "model.safetensors",
    capabilities: ["text_to_image"],
    confirmed: true,
  })
  wrapper.unmount()
})
