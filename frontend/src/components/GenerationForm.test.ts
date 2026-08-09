// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test } from "vitest"

import type { ModelItem } from "../lib/api"
import { createDefaultGenerationRequest } from "../stores/generation"
import GenerationForm from "./GenerationForm.vue"

const imageModel: ModelItem = {
  id: "image",
  name: "基础图片模型",
  kind: "checkpoint",
  usage: "image",
  filename: "image.safetensors",
  source: "comfyui",
  installed: true,
  path: null,
  description: "model",
  preview_url: null,
  size_label: null,
  reference_url: null,
  capability_profile: {
    capabilities: ["text_to_image", "image_to_image"],
    required_inputs: { image_to_image: ["reference_image"] },
    required_components: {},
    workflow_family: {
      text_to_image: "standard_checkpoint",
      image_to_image: "standard_checkpoint",
    },
    description_zh: "适合通用图片生成和重绘。",
    recommended_params: { image_to_image: { denoise: 0.5 } },
    confirmed: true,
  },
}

function mountForm(creationType: "text_to_image" | "image_to_image") {
  const form = createDefaultGenerationRequest()
  form.creation_type = creationType
  form.checkpoint = imageModel.filename
  return mount(GenerationForm, {
    props: {
      form,
      models: [imageModel],
      canGenerate: false,
      blockedReason: "",
      submissionAttempted: false,
      busy: false,
      notice: "",
      noticeType: "info",
      mode: "image",
    },
  })
}

test("图片页提供文生图和图生图任务选择", () => {
  const wrapper = mountForm("text_to_image")
  const selector = wrapper.find('[data-testid="creation-type-selector"]')

  expect(selector.exists()).toBe(true)
  expect(selector.text()).toContain("文生图")
  expect(selector.text()).toContain("图生图")
  expect(wrapper.text()).not.toContain("参考图（必填）")
})

test("图生图显示必填参考图和所选模型中文用途", () => {
  const wrapper = mountForm("image_to_image")

  expect(wrapper.text()).toContain("参考图（必填）")
  expect(wrapper.text()).toContain("适合通用图片生成和重绘。")
  expect(wrapper.text()).toContain("denoise：0.5")
})
