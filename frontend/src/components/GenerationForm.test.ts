// @vitest-environment happy-dom

import { mount } from "@vue/test-utils"
import { expect, test, vi } from "vitest"
import { Select, Switch, Upload } from "ant-design-vue"

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
    content_tags: ["general"],
    description_zh: "适合通用图片生成和重绘。",
    recommended_params: { image_to_image: { denoise: 0.5 } },
    confirmed: true,
  },
}

function mountForm(
  creationType: "text_to_image" | "image_to_image",
  models: ModelItem[] = [imageModel],
  checkpoint = imageModel.filename,
) {
  const form = createDefaultGenerationRequest()
  form.creation_type = creationType
  form.checkpoint = checkpoint
  return mount(GenerationForm, {
    props: {
      form,
      models,
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

test("新手选模按内容过滤模型并清空不匹配选择", async () => {
  const portraitModel: ModelItem = {
    ...imageModel,
    id: "portrait",
    name: "人物模型",
    filename: "portrait.safetensors",
    capability_profile: {
      ...imageModel.capability_profile,
      content_tags: ["portrait"],
    },
  }
  const landscapeModel: ModelItem = {
    ...imageModel,
    id: "landscape",
    name: "风景模型",
    filename: "landscape.safetensors",
    capability_profile: {
      ...imageModel.capability_profile,
      content_tags: ["landscape"],
    },
  }
  const wrapper = mountForm(
    "text_to_image",
    [portraitModel, landscapeModel, imageModel],
    landscapeModel.filename,
  )

  const category = wrapper.find('[data-testid="content-category-selector"]')
  const beginnerSwitch = wrapper.find('[data-testid="beginner-model-switch"]')
  expect(category.exists()).toBe(true)
  expect(beginnerSwitch.exists()).toBe(true)
  expect(beginnerSwitch.findComponent(Switch).props("checked")).toBe(true)

  category.findComponent(Select).vm.$emit("update:value", "portrait")
  await wrapper.vm.$nextTick()

  const modelSelector = wrapper.find('[data-testid="model-selector"]').findComponent(Select)
  const modelValues = modelSelector.props("options").map(
    (option: { value: string }) => option.value,
  )
  expect(modelValues).toContain("portrait.safetensors")
  expect(modelValues).toContain("image.safetensors")
  expect(modelValues).not.toContain("landscape.safetensors")
  expect(wrapper.props("form").checkpoint).toBe("")
})

test("条件图长文件名保持在预览卡片内并可查看完整名称", async () => {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:condition-preview"),
  })
  const wrapper = mountForm("text_to_image")
  const filename = `${"very-long-condition-image-name-".repeat(8)}.png`
  const file = new File(["image"], filename, { type: "image/png" })
  const upload = wrapper.findComponent(Upload)
  const beforeUpload = upload.props("beforeUpload") as (file: File) => boolean

  beforeUpload(file)
  await wrapper.vm.$nextTick()

  const name = wrapper.find(".reference-media-name")
  expect(name.text()).toBe(filename)
  expect(name.attributes("title")).toBe(filename)
})
