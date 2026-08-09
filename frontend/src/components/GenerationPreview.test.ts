// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test } from "vitest"

import { createDefaultGenerationRequest } from "../stores/generation"
import GenerationPreview from "./GenerationPreview.vue"

test("生成中使用标准居中加载图标", () => {
  const wrapper = mount(GenerationPreview, {
    props: {
      blockedReason: "",
      task: {
        id: "task-1",
        status: "running",
        progress: 35,
        request: createDefaultGenerationRequest(),
        prompt_id: "prompt-1",
        outputs: [],
        error: null,
      },
    },
  })

  expect(wrapper.find(".preview-loading-panel .ant-spin").exists()).toBe(true)
  expect(wrapper.find(".preview-orbit").exists()).toBe(false)
  expect(wrapper.find(".preview-loading-panel .ant-progress").exists()).toBe(false)
})
