import { describe, expect, it } from "vitest"
import {
  createDefaultGenerationRequest,
  canSubmitGeneration,
  getGenerationBlockedReason,
  upsertTask,
} from "./generation"
import type { GenerationTask } from "../lib/api"

const baseTask: GenerationTask = {
  id: "task-1",
  status: "queued",
  progress: 0,
  request: createDefaultGenerationRequest(),
  prompt_id: "prompt-1",
  outputs: [],
  error: null,
}

describe("generation store helpers", () => {
  it("creates a practical default text-to-image request", () => {
    const request = createDefaultGenerationRequest()

    expect(request.width).toBe(1024)
    expect(request.height).toBe(1024)
    expect(request.steps).toBe(25)
    expect(request.cfg).toBe(7)
    expect(request.seed).toBe(-1)
    expect(request.batch_size).toBe(1)
    expect(request.creation_type).toBe("text_to_image")
  })

  it("requires connection, prompt, checkpoint, and idle state before submission", () => {
    const request = createDefaultGenerationRequest()
    request.prompt = "pixel warrior"
    request.checkpoint = "model.safetensors"

    expect(canSubmitGeneration(request, true, false)).toBe(true)
    expect(canSubmitGeneration(request, false, false)).toBe(false)
    expect(canSubmitGeneration(request, true, true)).toBe(false)
    expect(canSubmitGeneration({ ...request, prompt: " " }, true, false)).toBe(false)
    expect(canSubmitGeneration({ ...request, checkpoint: "" }, true, false)).toBe(false)
  })

  it("returns the first clear reason when generation is blocked", () => {
    const request = createDefaultGenerationRequest()

    expect(getGenerationBlockedReason(request, false, false, [])).toBe(
      "请先在连接设置中完成 ComfyUI 连接",
    )

    request.prompt = "pixel warrior"
    expect(getGenerationBlockedReason(request, true, false, [])).toBe(
      "当前没有可用模型，请检查 ComfyUI 模型目录",
    )

    expect(getGenerationBlockedReason(request, true, true, ["model.safetensors"])).toBe(
      "正在生成，请稍候",
    )

    request.checkpoint = "model.safetensors"
    expect(getGenerationBlockedReason(request, true, false, ["model.safetensors"])).toBe("")
  })

  it("adds new tasks first and replaces existing tasks in place", () => {
    const updatedTask = { ...baseTask, status: "completed" as const, progress: 100 }
    const first = upsertTask([], baseTask)
    const second = upsertTask(first, updatedTask)

    expect(first).toHaveLength(1)
    expect(second).toHaveLength(1)
    expect(second[0]).toMatchObject({ id: "task-1", status: "completed", progress: 100 })
  })

  it("validates required media from the explicit creation type", () => {
    const request = createDefaultGenerationRequest()
    request.prompt = "pixel warrior"
    request.checkpoint = "model.safetensors"
    request.creation_type = "image_to_image"

    expect(canSubmitGeneration(request, true, false)).toBe(false)
    expect(getGenerationBlockedReason(request, true, false, [request.checkpoint])).toBe(
      "请上传参考图",
    )

    request.reference_image = "ref.png"
    expect(canSubmitGeneration(request, true, false)).toBe(true)

    request.creation_type = "video_to_video"
    request.reference_video = ""
    expect(canSubmitGeneration(request, true, false)).toBe(false)
    expect(getGenerationBlockedReason(request, true, false, [request.checkpoint])).toBe(
      "请上传参考视频",
    )
  })

  it("blocks submission when a condition image has no ControlNet model", () => {
    const request = createDefaultGenerationRequest()
    request.prompt = "pixel warrior"
    request.checkpoint = "model.safetensors"
    request.controlnet = {
      model: "",
      preprocessor: "canny",
      image: "condition.png",
      strength: 1,
      start_percent: 0,
      end_percent: 1,
    }

    expect(canSubmitGeneration(request, true, false)).toBe(false)
    expect(getGenerationBlockedReason(request, true, false, [request.checkpoint])).toBe(
      "请选择 ControlNet 模型",
    )
  })
})
