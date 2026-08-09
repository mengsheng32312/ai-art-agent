import { describe, expect, it } from "vitest"
import type { GenerationRequest, ModelItem } from "./api"
import {
  applyCreationType,
  filterModelsForCreationType,
} from "./modelCapabilities"
import { createDefaultGenerationRequest } from "../stores/generation"

function model(
  filename: string,
  capabilities: ModelItem["capability_profile"]["capabilities"],
  confirmed = true,
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
