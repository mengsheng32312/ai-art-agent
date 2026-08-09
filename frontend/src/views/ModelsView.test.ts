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
    },
  })

  expect(wrapper.text()).toContain("ComfyUI 可用模型")
  expect(wrapper.text()).not.toContain("远程可用模型")
})
