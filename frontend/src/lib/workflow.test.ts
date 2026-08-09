import { describe, expect, it } from "vitest"
import { parseWorkflowFile } from "./workflow"

const imageWorkflow = {
  workflow: {
    last_node_id: 7,
    nodes: [
      { id: 1, type: "CheckpointLoaderSimple", inputs: { ckpt_name: "model.safetensors" } },
      { id: 2, type: "CLIPTextEncode", inputs: { text: "mountain lake", clip: ["1", 1] } },
      { id: 3, type: "CLIPTextEncode", inputs: { text: "blurry", clip: ["1", 1] } },
      { id: 4, type: "EmptyLatentImage", inputs: { width: 768, height: 512, batch_size: 2 } },
      {
        id: 5,
        type: "KSampler",
        inputs: {
          seed: 42,
          steps: 30,
          cfg: 7.5,
          sampler_name: "dpmpp_2m",
          scheduler: "karras",
          denoise: 1,
          positive: ["2", 0],
          negative: ["3", 0],
        },
      },
      { id: 6, type: "VAEDecode", inputs: { samples: ["5", 0], vae: ["1", 2] } },
      { id: 7, type: "SaveImage", inputs: { filename_prefix: "AIArtAgent", images: ["6", 0] } },
    ],
  },
}

const videoWorkflow = {
  workflow: {
    last_node_id: 8,
    nodes: [
      { id: 1, type: "CheckpointLoaderSimple", inputs: { ckpt_name: "mm_sd_v15.safetensors" } },
      { id: 2, type: "CLIPTextEncode", inputs: { text: "sunset", clip: ["1", 1] } },
      { id: 3, type: "CLIPTextEncode", inputs: { text: "noise", clip: ["1", 1] } },
      {
        id: 4,
        type: "ADE_AnimateDiffLoaderGen1",
        inputs: { model: ["1", 0], model_name: "mm_sd_v15_v2.ckpt", beta_schedule: "sqrt_linear (AnimateDiff)" },
      },
      { id: 5, type: "EmptyLatentImage", inputs: { width: 512, height: 512, batch_size: 16 } },
      {
        id: 6,
        type: "KSampler",
        inputs: {
          seed: 7,
          steps: 20,
          cfg: 6,
          sampler_name: "euler",
          scheduler: "normal",
          denoise: 0.8,
          positive: ["2", 0],
          negative: ["3", 0],
        },
      },
      { id: 7, type: "VAEDecode", inputs: { samples: ["6", 0], vae: ["1", 2] } },
      {
        id: 8,
        type: "SaveAnimatedWEBP",
        inputs: { images: ["7", 0], fps: 8, lossless: false, quality: 80, method: "default", filename_prefix: "AIArtAgent" },
      },
    ],
  },
}

describe("parseWorkflowFile", () => {
  it("parses an exported image workflow", () => {
    const parsed = parseWorkflowFile(imageWorkflow)

    expect(parsed.mediaType).toBe("image")
    expect(parsed.creationType).toBe("text_to_image")
    expect(parsed.fields).toMatchObject({
      checkpoint: "model.safetensors",
      prompt: "mountain lake",
      negative_prompt: "blurry",
      width: 768,
      height: 512,
      batch_size: 2,
      seed: 42,
      steps: 30,
      cfg: 7.5,
      sampler: "dpmpp_2m",
      scheduler: "karras",
      output_prefix: "AIArtAgent",
    })
  })

  it("parses an exported video workflow", () => {
    const parsed = parseWorkflowFile(videoWorkflow)

    expect(parsed.mediaType).toBe("video")
    expect(parsed.creationType).toBe("text_to_video")
    expect(parsed.fields).toMatchObject({
      motion_model: "mm_sd_v15_v2.ckpt",
      beta_schedule: "sqrt_linear (AnimateDiff)",
      frames: 16,
      denoise: 0.8,
      fps: 8,
      lossless: false,
      quality: 80,
      method: "default",
    })
    expect(parsed.fields.batch_size).toBeUndefined()
  })

  it("recognizes image-to-image from LoadImage and VAEEncode nodes", () => {
    const parsed = parseWorkflowFile({
      nodes: [
        { type: "CheckpointLoaderSimple", inputs: { ckpt_name: "image.safetensors" } },
        { type: "LoadImage", inputs: { image: "reference.png" } },
        { type: "VAEEncode", inputs: { pixels: ["2", 0] } },
        { type: "SaveImage", inputs: {} },
      ],
    })

    expect(parsed.creationType).toBe("image_to_image")
    expect(parsed.fields).toMatchObject({
      creation_type: "image_to_image",
      reference_image: "reference.png",
    })
  })

  it("recognizes Wan image-to-video and video-to-video workflows", () => {
    const imageToVideo = parseWorkflowFile({
      nodes: [
        { type: "UNETLoader", inputs: { unet_name: "wan-i2v.safetensors" } },
        { type: "LoadImage", inputs: { image: "start.png" } },
        { type: "WanImageToVideo", inputs: {} },
        { type: "SaveAnimatedWEBP", inputs: {} },
      ],
    })
    const videoToVideo = parseWorkflowFile({
      nodes: [
        { type: "UNETLoader", inputs: { unet_name: "wan-v2v.safetensors" } },
        { type: "LoadVideo", inputs: { video: "source.mp4" } },
        { type: "WanVideoToVideo", inputs: {} },
        { type: "SaveAnimatedWEBP", inputs: {} },
      ],
    })

    expect(imageToVideo.fields).toMatchObject({
      creation_type: "image_to_video",
      checkpoint: "wan-i2v.safetensors",
      reference_image: "start.png",
    })
    expect(videoToVideo.fields).toMatchObject({
      creation_type: "video_to_video",
      checkpoint: "wan-v2v.safetensors",
      reference_video: "source.mp4",
    })
  })

  it("matches CLIP texts by sampler references regardless of node order", () => {
    const shuffled = {
      nodes: [
        { id: 9, type: "SaveImage", inputs: { filename_prefix: "AIArtAgent" } },
        { id: 3, type: "CLIPTextEncode", inputs: { text: "negative text", clip: ["1", 1] } },
        { id: 2, type: "CLIPTextEncode", inputs: { text: "positive text", clip: ["1", 1] } },
        {
          id: 5,
          type: "KSampler",
          inputs: { positive: ["2", 0], negative: ["3", 0], seed: 1, steps: 20, cfg: 7, sampler_name: "euler", scheduler: "normal", denoise: 1 },
        },
      ],
    }

    const parsed = parseWorkflowFile(shuffled)

    expect(parsed.fields.prompt).toBe("positive text")
    expect(parsed.fields.negative_prompt).toBe("negative text")
  })
})
