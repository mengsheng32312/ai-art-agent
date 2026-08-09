// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test } from "vitest"

import SettingsView from "./SettingsView.vue"

test("测试本地连接时只在连接状态区域展示检查进度", () => {
  const wrapper = mount(SettingsView, {
    props: {
      config: {
        mode: "local",
        comfyui_path: "D:\\ComfyUI",
        local_model_path: null,
        api_url: "http://127.0.0.1:8188",
      },
      connected: false,
      connectionMessage: "正在检查本地 ComfyUI...",
      busy: false,
      testingConnection: true,
      notice: "正在检查本地 ComfyUI...",
      noticeType: "info",
      settingsError: "",
    },
  })

  expect(wrapper.findAll(".ant-alert")).toHaveLength(1)
  expect(wrapper.get(".ant-alert").text()).toContain("正在检查本地 ComfyUI...")
})

test("本地模式可以单独选择本地模型目录", async () => {
  const wrapper = mount(SettingsView, {
    props: {
      config: {
        mode: "local",
        comfyui_path: "D:\\ComfyUI",
        local_model_path: null,
        api_url: "http://127.0.0.1:8188",
      },
      connected: false,
      connectionMessage: "尚未连接",
      busy: false,
      testingConnection: false,
      notice: "",
      noticeType: "info",
      settingsError: "",
    },
  })

  const chooseModelButton = wrapper.findAll("button").find(button =>
    button.text().includes("选择模型目录"),
  )
  expect(chooseModelButton).toBeDefined()
  await chooseModelButton?.trigger("click")
  expect(wrapper.emitted("chooseModelDirectory")).toHaveLength(1)
})
