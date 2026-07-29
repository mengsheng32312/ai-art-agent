<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { Image, Settings, History, Sparkles, CircleCheck, CircleX, LoaderCircle } from "lucide-vue-next"
import { api, type Config, type GenerationRequest, type GenerationTask } from "./lib/api"
import {
  prepareDesktopAgent,
  selectComfyuiDirectory,
  startComfyui,
  takeDesktopStartupError,
} from "./lib/desktop"

type Page = "generate" | "history" | "settings"
const page = ref<Page>("generate")
const connected = ref(false)
const connectionMessage = ref("正在检测…")
const checkpoints = ref<string[]>([])
const history = ref<GenerationTask[]>([])
const currentTask = ref<GenerationTask | null>(null)
const busy = ref(false)
const notice = ref("")
const startupError = ref("")
const localApiUrl = "http://127.0.0.1:8188"
const config = reactive<Config>({ mode: "remote", comfyui_path: null, api_url: "http://127.0.0.1:8188" })
const form = reactive<GenerationRequest>({
  prompt: "",
  negative_prompt: "",
  checkpoint: "",
  width: 1024,
  height: 1024,
  steps: 25,
  cfg: 7,
  seed: -1,
  sampler: "euler",
  scheduler: "normal",
  batch_size: 1,
})

const canGenerate = computed(() => connected.value && form.prompt.trim() && form.checkpoint && !busy.value)
const canSave = computed(
  () =>
    Boolean(config.api_url.trim()) &&
    (config.mode === "remote" || Boolean(config.comfyui_path?.trim())),
)

async function refreshConnection(): Promise<boolean> {
  connectionMessage.value = "正在检测…"
  try {
    const state = await api.status()
    connected.value = state.connected
    connectionMessage.value = state.message
    checkpoints.value = state.connected ? await api.checkpoints() : []
    if (!form.checkpoint && checkpoints.value.length) form.checkpoint = checkpoints.value[0]
    return state.connected
  } catch (error) {
    connected.value = false
    connectionMessage.value = error instanceof Error ? error.message : "连接失败"
    return false
  }
}

async function waitForComfyui(): Promise<boolean> {
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await refreshConnection()) return true
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  return false
}

async function saveSettings() {
  busy.value = true
  try {
    if (config.mode === "local") config.api_url = localApiUrl
    await api.saveConfig(config)
    if (config.mode === "local" && config.comfyui_path) {
      await startComfyui(config.comfyui_path)
      notice.value = "设置已保存，正在等待 ComfyUI 启动…"
      const ready = await waitForComfyui()
      notice.value = ready ? "设置已保存" : "设置已保存，但 ComfyUI 启动超时"
    } else {
      notice.value = "设置已保存"
      await refreshConnection()
    }
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "保存失败"
  } finally {
    busy.value = false
  }
}

function setMode(mode: Config["mode"]) {
  config.mode = mode
  if (mode === "local") config.api_url = localApiUrl
}

async function chooseComfyuiDirectory() {
  try {
    const selected = await selectComfyuiDirectory()
    if (selected) config.comfyui_path = selected
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error)
  }
}

async function generate() {
  busy.value = true
  notice.value = ""
  try {
    const task = await api.generate(form)
    currentTask.value = task
    history.value.unshift(task)
    notice.value = `任务已提交：${task.prompt_id}`
    for (let attempt = 0; attempt < 360 && currentTask.value.status !== "completed"; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      currentTask.value = await api.generation(task.id)
      const index = history.value.findIndex(item => item.id === task.id)
      if (index >= 0) history.value[index] = currentTask.value
      if (currentTask.value.status === "failed") break
    }
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "提交失败"
  } finally {
    busy.value = false
  }
}

async function loadInitialState() {
  startupError.value = ""
  connectionMessage.value = "正在检测…"
  try {
    const desktopError = takeDesktopStartupError()
    if (desktopError) throw new Error(desktopError)
    Object.assign(config, await api.config())
    history.value = await api.history()
    await refreshConnection()
  } catch (error) {
    connected.value = false
    startupError.value = error instanceof Error ? error.message : String(error)
    connectionMessage.value = startupError.value
    notice.value = `本地 Agent 不可用：${startupError.value}`
  }
}

async function retryInitialState() {
  startupError.value = ""
  try {
    await prepareDesktopAgent()
    await loadInitialState()
  } catch (error) {
    connected.value = false
    startupError.value = error instanceof Error ? error.message : String(error)
    connectionMessage.value = startupError.value
    notice.value = `本地 Agent 不可用：${startupError.value}`
  }
}

onMounted(loadInitialState)
</script>

<template>
  <div class="shell">
    <aside>
      <div class="brand"><span><Sparkles :size="19" /></span><div>AI Art Agent<small>创作工作台</small></div></div>
      <nav>
        <button :class="{ active: page === 'generate' }" @click="page = 'generate'"><Image :size="18" />图片生成</button>
        <button :class="{ active: page === 'history' }" @click="page = 'history'"><History :size="18" />历史记录</button>
        <button :class="{ active: page === 'settings' }" @click="page = 'settings'"><Settings :size="18" />连接设置</button>
      </nav>
      <div class="connection" :class="{ online: connected }">
        <CircleCheck v-if="connected" :size="18" /><CircleX v-else :size="18" />
        <div><strong>{{ connected ? "ComfyUI 已连接" : "ComfyUI 未连接" }}</strong><small>{{ connectionMessage }}</small><button v-if="startupError" class="retry" @click="retryInitialState">重试</button></div>
      </div>
    </aside>

    <main>
      <template v-if="page === 'generate'">
        <header><div><p class="eyebrow">CREATE</p><h1>生成图片</h1><p>描述你的想法，其余交给工作流。</p></div></header>
        <div class="grid">
          <section class="card form-card">
            <label>画面描述<textarea v-model="form.prompt" rows="5" placeholder="例如：薄雾中的东方古城，电影级光影…"></textarea></label>
            <label>排除内容<textarea v-model="form.negative_prompt" rows="2" placeholder="模糊、低质量、文字…"></textarea></label>
            <div class="row">
              <label>模型<select v-model="form.checkpoint"><option disabled value="">请选择 checkpoint</option><option v-for="item in checkpoints" :key="item">{{ item }}</option></select></label>
              <label>生成数量<input v-model.number="form.batch_size" type="number" min="1" max="8" /></label>
            </div>
            <div class="row thirds">
              <label>宽度<input v-model.number="form.width" type="number" step="64" /></label>
              <label>高度<input v-model.number="form.height" type="number" step="64" /></label>
              <label>随机种子<input v-model.number="form.seed" type="number" /></label>
            </div>
            <details>
              <summary>高级参数</summary>
              <div class="row thirds advanced">
                <label>步数<input v-model.number="form.steps" type="number" /></label>
                <label>CFG<input v-model.number="form.cfg" type="number" step="0.5" /></label>
                <label>采样器<select v-model="form.sampler"><option>euler</option><option>dpmpp_2m</option></select></label>
                <label>调度器<select v-model="form.scheduler"><option>normal</option><option>karras</option><option>exponential</option><option>sgm_uniform</option></select></label>
              </div>
            </details>
            <button class="primary" :disabled="!canGenerate" @click="generate"><LoaderCircle v-if="busy" class="spin" :size="18" /><Sparkles v-else :size="18" />{{ busy ? "正在提交" : "开始生成" }}</button>
            <p v-if="notice" class="notice">{{ notice }}</p>
          </section>
          <section class="card preview">
            <img v-if="currentTask?.outputs[0]" :src="currentTask.outputs[0]" alt="生成结果" />
            <div v-else class="empty">
              <CircleX v-if="currentTask?.status === 'failed'" :size="34" />
              <LoaderCircle v-else-if="currentTask" class="spin" :size="34" />
              <Image v-else :size="34" />
              <strong>{{ currentTask?.status === "failed" ? "生成失败" : currentTask ? "正在生成" : "等待创作" }}</strong>
              <p v-if="currentTask?.status === 'failed'">{{ currentTask.error }}</p>
              <p v-else>{{ currentTask ? `${currentTask.status} · ${currentTask.progress}%` : "生成结果会显示在这里" }}</p>
            </div>
          </section>
        </div>
      </template>

      <template v-else-if="page === 'history'">
        <header><div><p class="eyebrow">LIBRARY</p><h1>历史记录</h1><p>最近提交的生成任务。</p></div></header>
        <div class="history-grid">
          <article v-for="item in history" :key="item.id" class="card history-item">
            <div class="thumb">
              <img v-if="item.outputs[0]" :src="item.outputs[0]" alt="历史生成结果" />
              <Image v-else :size="28" />
            </div><strong>{{ item.request.prompt }}</strong>
            <small>{{ item.request.checkpoint }} · {{ item.request.width }}×{{ item.request.height }}</small>
            <span class="badge">{{ item.status }}</span>
          </article>
          <div v-if="!history.length" class="card empty-list">还没有生成记录</div>
        </div>
      </template>

      <template v-else>
        <header><div><p class="eyebrow">SETTINGS</p><h1>连接设置</h1><p>连接本机或其他电脑上的 ComfyUI。</p></div></header>
        <section class="card settings-card">
          <div class="segmented"><button :class="{ selected: config.mode === 'local' }" @click="setMode('local')">本地 ComfyUI</button><button :class="{ selected: config.mode === 'remote' }" @click="setMode('remote')">远程 API</button></div>
          <label v-if="config.mode === 'local'">ComfyUI 安装目录<div class="path-row"><input v-model="config.comfyui_path" placeholder="D:\ComfyUI" /><button class="secondary" @click="chooseComfyuiDirectory">选择目录</button></div></label>
          <label>API 地址<input v-model="config.api_url" placeholder="http://127.0.0.1:8188" /></label>
          <div class="actions"><button class="secondary" @click="refreshConnection">测试连接</button><button class="primary compact" :disabled="busy || !canSave" @click="saveSettings">保存设置</button></div>
          <p v-if="notice" class="notice">{{ notice }}</p>
        </section>
      </template>
    </main>
  </div>
</template>
