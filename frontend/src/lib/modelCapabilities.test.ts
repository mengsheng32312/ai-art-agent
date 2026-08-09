import { describe, expect, it } from "vitest"
import type { ContentTag, GenerationRequest, ModelItem } from "./api"
import {
  applyCreationType,
  filterModelsForContent,
  filterModelsForCreationType,
} from "./modelCapabilities"
import { createDefaultGenerationRequest } from "../stores/generation"

function model(
  filename: string,
  capabilities: ModelItem["capability_profile"]["capabilities"],
  confirmed = true,
  contentTags: ContentTag[] = ["general"],
): ModelItem {
  return {
    id: filename,
    name: filename,
    kind: "checkpoint",
    usage: "image",
    filename,
    source: "comfyui",
    installed: true,
    path: null,
    description: "model",
    preview_url: null,
    size_label: null,
    reference_url: null,
    capability_profile: {
      capabilities,
      required_inputs: {},
      required_components: {},
      workflow_family: {},
      content_tags: contentTags,
      description_zh: "用途说明",
      recommended_params: {},
      confirmed,
    },
  }
}

describe("model capability helpers", () => {
  it("returns only confirmed models supporting the selected creation type", () => {
    const models = [
      model("image.safetensors", ["text_to_image", "image_to_image"]),
      model("video.safetensors", ["image_to_video"]),
      model("pending.safetensors", ["text_to_image"], false),
    ]

    expect(filterModelsForCreationType(models, "text_to_image").map(item => item.filename))
      .toEqual(["image.safetensors"])
    expect(filterModelsForCreationType(models, "image_to_video").map(item => item.filename))
      .toEqual(["video.safetensors"])
  })

  it("新手模式保留精准与通用模型并优先精准匹配", () => {
    const models = [
      model("general.safetensors", ["text_to_image"]),
      model("landscape.safetensors", ["text_to_image"], true, ["landscape"]),
      model("portrait.safetensors", ["text_to_image"], true, ["portrait"]),
    ]

    expect(
      filterModelsForContent(models, "text_to_image", "portrait", true).map(
        item => item.filename,
      ),
    ).toEqual(["portrait.safetensors", "general.safetensors"])
  })

  it("关闭新手模式后显示全部创作任务兼容模型", () => {
    const models = [
      model("portrait.safetensors", ["text_to_image"], true, ["portrait"]),
      model("landscape.safetensors", ["text_to_image"], true, ["landscape"]),
      model("general.safetensors", ["text_to_image"]),
    ]

    expect(
      filterModelsForContent(models, "text_to_image", "portrait", false).map(
        item => item.filename,
      ),
    ).toEqual([
      "portrait.safetensors",
      "landscape.safetensors",
      "general.safetensors",
    ])
  })

  it("选择通用内容时不隐藏专用模型", () => {
    const models = [
      model("portrait.safetensors", ["text_to_image"], true, ["portrait"]),
      model("landscape.safetensors", ["text_to_image"], true, ["landscape"]),
      model("general.safetensors", ["text_to_image"]),
    ]

    expect(
      filterModelsForContent(models, "text_to_image", "general", true).map(
        item => item.filename,
      ),
    ).toEqual([
      "portrait.safetensors",
      "landscape.safetensors",
      "general.safetensors",
    ])
  })

  it("clears incompatible model and stale reference inputs when task changes", () => {
    const request: GenerationRequest = {
      ...createDefaultGenerationRequest(),
      checkpoint: "video.safetensors",
      creation_type: "video_to_video",
      media_type: "video",
      video_mode: "v2v",
      reference_image: "old.png",
      reference_video: "old.mp4",
    }
    const models = [model("video.safetensors", ["video_to_video"])]

    applyCreationType(request, "text_to_image", models)

    expect(request.creation_type).toBe("text_to_image")
    expect(request.media_type).toBe("image")
    expect(request.video_mode).toBe("t2v")
    expect(request.checkpoint).toBe("")
    expect(request.reference_image).toBe("")
    expect(request.reference_video).toBe("")
  })
})
