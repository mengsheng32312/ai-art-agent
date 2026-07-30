import { flushPromises, mount } from "@vue/test-utils"
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest"

import App from "./App.vue"
import { api, type GenerationTask } from "./lib/api"

vi.mock("./lib/api", () => ({
  api: {
    config: vi.fn(),
    saveConfig: vi.fn(),
    status: vi.fn(),
    checkpoints: vi.fn(),
    generate: vi.fn(),
    generation: vi.fn(),
    history: vi.fn(),
  },
}))

const mockedApi = vi.mocked(api)

const queuedTask: GenerationTask = {
  id: "task-1",
  status: "queued",
  progress: 0,
  request: {
    prompt: "a red fox",
    negative_prompt: "",
    checkpoint: "model.safetensors",
    width: 1024,
    height: 1024,
    steps: 25,
    cfg: 7,
    seed: -1,
    sampler: "euler",
    scheduler: "normal",
    batch_size: 1,
  },
  prompt_id: "prompt-1",
  outputs: [],
  error: null,
}

async function mountApp() {
  const wrapper = mount(App)
  await flushPromises()
  return wrapper
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll("button").find((item) => item.text().includes(text))
  if (!button) throw new Error(`Button not found: ${text}`)
  return button
}

beforeEach(() => {
  mockedApi.config.mockResolvedValue({
    mode: "remote",
    comfyui_path: null,
    api_url: "http://127.0.0.1:8188",
  })
  mockedApi.saveConfig.mockImplementation(async (config) => config)
  mockedApi.status.mockResolvedValue({ connected: true, message: "ComfyUI 已连接" })
  mockedApi.checkpoints.mockResolvedValue(["model.safetensors"])
  mockedApi.history.mockResolvedValue([])
  mockedApi.generate.mockResolvedValue(queuedTask)
})

afterEach(() => {
  vi.useRealTimers()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
  delete (window as Window & { __TAURI__?: unknown }).__TAURI__
})

describe("settings flow", () => {
  test("disables saving local mode until a ComfyUI directory is selected", async () => {
    const wrapper = await mountApp()
    await buttonByText(wrapper, "连接设置").trigger("click")
    await buttonByText(wrapper, "本地 ComfyUI").trigger("click")

    expect(buttonByText(wrapper, "保存设置").attributes("disabled")).toBeDefined()
  })

  test("selects a local ComfyUI directory through the desktop command", async () => {
    const invoke = vi.fn().mockResolvedValue("D:\\ComfyUI")
    ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
      core: { invoke },
    }
    const wrapper = await mountApp()
    await buttonByText(wrapper, "连接设置").trigger("click")
    await buttonByText(wrapper, "本地 ComfyUI").trigger("click")

    await buttonByText(wrapper, "选择目录").trigger("click")
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith("select_comfyui_directory")
    const pathInput = wrapper
      .findAll("input")
      .find((input) => input.attributes("placeholder") === "D:\\ComfyUI")
    expect(pathInput?.element.value).toBe("D:\\ComfyUI")
  })

  test("starts the selected ComfyUI after saving local mode", async () => {
    mockedApi.config.mockResolvedValue({
      mode: "remote",
      comfyui_path: null,
      api_url: "http://remote-comfy:8188",
    })
    const invoke = vi.fn(async (command: string) => {
      if (command === "select_comfyui_directory") return "D:\\ComfyUI"
      if (command === "start_comfyui") return 42
      return null
    })
    ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
      core: { invoke },
    }
    const wrapper = await mountApp()
    await buttonByText(wrapper, "连接设置").trigger("click")
    await buttonByText(wrapper, "本地 ComfyUI").trigger("click")
    await buttonByText(wrapper, "选择目录").trigger("click")
    await flushPromises()

    await buttonByText(wrapper, "保存设置").trigger("click")
    await flushPromises()

    expect(invoke).toHaveBeenCalledWith("start_comfyui", {
      path: "D:\\ComfyUI",
    })
    expect(mockedApi.saveConfig).toHaveBeenCalledWith({
      mode: "local",
      comfyui_path: "D:\\ComfyUI",
      api_url: "http://127.0.0.1:8188",
    })
  })

  test("waits for a newly started local ComfyUI to become ready", async () => {
    vi.useFakeTimers()
    mockedApi.status
      .mockResolvedValueOnce({ connected: true, message: "existing connection" })
      .mockResolvedValueOnce({ connected: false, message: "starting" })
      .mockResolvedValueOnce({ connected: true, message: "ready" })
    const invoke = vi.fn(async (command: string) => {
      if (command === "select_comfyui_directory") return "D:\\ComfyUI"
      if (command === "start_comfyui") return 42
      return null
    })
    ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
      core: { invoke },
    }
    const wrapper = await mountApp()
    await buttonByText(wrapper, "连接设置").trigger("click")
    await buttonByText(wrapper, "本地 ComfyUI").trigger("click")
    await buttonByText(wrapper, "选择目录").trigger("click")
    await flushPromises()

    await buttonByText(wrapper, "保存设置").trigger("click")
    await flushPromises()
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(mockedApi.status).toHaveBeenCalledTimes(3)
    expect(wrapper.text()).toContain("ready")
  })
})

describe("generation flow", () => {
  test("exposes the scheduler in advanced parameters", async () => {
    const wrapper = await mountApp()

    expect(wrapper.text()).toContain("调度器")
  })

  test("shows the ComfyUI execution error when polling returns a failed task", async () => {
    vi.useFakeTimers()
    mockedApi.generation.mockResolvedValue({
      ...queuedTask,
      status: "failed",
      error: "CUDA out of memory",
    })
    const wrapper = await mountApp()
    await wrapper.get("textarea").setValue("a red fox")
    await buttonByText(wrapper, "开始生成").trigger("click")
    await flushPromises()

    await vi.advanceTimersByTimeAsync(1000)
    await flushPromises()

    expect(wrapper.text()).toContain("CUDA out of memory")
  })

  test("polls until the completed image is displayed", async () => {
    vi.useFakeTimers()
    mockedApi.generation
      .mockResolvedValueOnce({ ...queuedTask, status: "running", progress: 1 })
      .mockResolvedValueOnce({
        ...queuedTask,
        status: "completed",
        progress: 100,
        outputs: ["http://comfy/view?filename=fox.png"],
      })
    const wrapper = await mountApp()
    await wrapper.get("textarea").setValue("a red fox")
    await buttonByText(wrapper, "开始生成").trigger("click")
    await flushPromises()

    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()

    expect(wrapper.get('img[alt="生成结果"]').attributes("src")).toContain("fox.png")
    expect(mockedApi.generation).toHaveBeenCalledTimes(2)
  })
})

describe("history flow", () => {
  test("renders persisted output thumbnails", async () => {
    mockedApi.history.mockResolvedValue([
      {
        ...queuedTask,
        status: "completed",
        progress: 100,
        outputs: ["http://comfy/view?filename=fox.png"],
      },
    ])
    const wrapper = await mountApp()

    await buttonByText(wrapper, "历史记录").trigger("click")

    expect(wrapper.get('img[alt="历史生成结果"]').attributes("src")).toContain(
      "fox.png",
    )
  })
})

test("shows an actionable error when the local Agent is unavailable", async () => {
  mockedApi.config.mockRejectedValue(new Error("Agent connection refused"))

  const wrapper = await mountApp()

  expect(wrapper.text()).toContain("Agent connection refused")
  expect(wrapper.text()).toContain("重试")
})

test("restarts the desktop Agent before retrying initial state", async () => {
  mockedApi.config
    .mockRejectedValueOnce(new Error("Agent connection refused"))
    .mockResolvedValueOnce({
      mode: "remote",
      comfyui_path: null,
      api_url: "http://127.0.0.1:8188",
    })
  const invoke = vi.fn().mockResolvedValue({
    pid: 42,
    port: 8001,
    baseUrl: "http://127.0.0.1:8001",
  })
  ;(window as Window & { __TAURI__?: unknown }).__TAURI__ = {
    core: { invoke },
  }
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        '{"status":"ok","service":"ai-art-agent","version":"0.1.0"}',
        { status: 200 },
      ),
    ),
  )
  const wrapper = await mountApp()

  await wrapper.get("button.retry").trigger("click")
  await flushPromises()

  expect(invoke).toHaveBeenCalledWith("start_local_agent")
  expect(mockedApi.config).toHaveBeenCalledTimes(2)
  expect(wrapper.find("button.retry").exists()).toBe(false)
})
