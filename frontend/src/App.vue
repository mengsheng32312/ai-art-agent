<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { Button, Layout, message, Space, Tag } from "ant-design-vue"
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons-vue"
import AppSidebar from "./components/AppSidebar.vue"
import {
  isDesktop,
  openInExplorer,
  selectComfyuiDirectory,
  startComfyui,
  takeDesktopStartupError,
} from "./lib/desktop"
import {
  api,
  resolveSaveLocation,
  type Config,
  type GenerationTask,
  type ModelCatalogResponse,
  type ModelItem,
} from "./lib/api"
import {
  canSubmitGeneration,
  createDefaultGenerationRequest,
  getGenerationBlockedReason,
  upsertTask,
} from "./stores/generation"
import type { Page } from "./types"
import GenerateView from "./views/GenerateView.vue"
import VideoView from "./views/VideoView.vue"
import HistoryView from "./views/HistoryView.vue"
import ModelsView from "./views/ModelsView.vue"
import SettingsView from "./views/SettingsView.vue"

const page = ref<Page>("generate")
const sidebarCollapsed = ref(false)
const connected = ref(false)
const connectionMessage = ref("尚未连接")
const settingsError = ref("")
const checkpoints = ref<string[]>([])
const motionModels = ref<string[]>([])
const vaeModels = ref<string[]>([])
const modelCatalog = ref<ModelCatalogResponse>({
  connected: false,
  manager_available: false,
  message: "请先连接 ComfyUI",
  local_models: [],
  online_models: [],
})
const history = ref<GenerationTask[]>([])
const currentTask = ref<GenerationTask | null>(null)
const busy = ref(false)
const testingConnection = ref(false)
const loadingModels = ref(false)
const downloadingModelId = ref("")
const notice = ref("")
const noticeType = ref<"info" | "success" | "error">("info")
const submissionAttempted = ref(false)
const startupError = ref("")
const localApiUrl = "http://127.0.0.1:8188"

const pageMeta: Record<Page, { label: string; hint: string }> = {
  generate: { label: "图片生成", hint: "参数与预览" },
  video: { label: "视频生成", hint: "AnimateDiff" },
  models: { label: "模型管理", hint: "本地与在线模型" },
  history: { label: "历史记录", hint: "结果与工作流" },
  settings: { label: "连接设置", hint: "ComfyUI" },
}

const quickPages: Array<{ label: string; value: Page }> = [
  { label: "生成", value: "generate" },
  { label: "模型", value: "models" },
  { label: "设置", value: "settings" },
]

const config = reactive<Config>({
  mode: "remote",
  comfyui_path: null,
  api_url: "http://127.0.0.1:8188",
})

const form = reactive(createDefaultGenerationRequest())
const canGenerate = computed(() => canSubmitGeneration(form, connected.value, busy.value))
const generationBlockedReason = computed(() =>
  getGenerationBlockedReason(form, connected.value, busy.value, checkpoints.value),
)

const videoForm = reactive({
  ...createDefaultGenerationRequest(),
  media_type: "video" as const,
  width: 512,
  height: 512,
  frames: 16,
})
const videoTask = ref<GenerationTask | null>(null)
const videoBusy = ref(false)
const videoNotice = ref("")
const videoNoticeType = ref<"info" | "success" | "error">("info")
const videoSubmissionAttempted = ref(false)
const canGenerateVideo = computed(() =>
  canSubmitGeneration(videoForm, connected.value, videoBusy.value),
)
const videoBlockedReason = computed(() =>
  getGenerationBlockedReason(
    videoForm,
    connected.value,
    videoBusy.value,
    checkpoints.value,
  ),
)

function clearActionState() {
  settingsError.value = ""
  notice.value = ""
  noticeType.value = "info"
}

function validateSettings() {
  settingsError.value = ""
  if (config.mode === "local" && !config.comfyui_path?.trim()) {
    const actionName = "测试连接"
    settingsError.value = `${actionName}失败：请选择 ComfyUI 安装目录`
    connected.value = false
    message.warning(settingsError.value)
    return false
  }
  if (config.mode === "remote" && !config.api_url.trim()) {
    const actionName = "测试连接"
    settingsError.value = `${actionName}失败：请输入 API 地址`
    connected.value = false
    message.warning(settingsError.value)
    return false
  }
  return true
}

async function checkConnection() {
  connectionMessage.value = "正在测试连接..."
  try {
    const state = await api.status()
    connected.value = state.connected
    connectionMessage.value = state.message
    checkpoints.value = state.connected ? await api.checkpoints() : []
    if (!form.checkpoint && checkpoints.value.length) form.checkpoint = checkpoints.value[0]
  } catch (error) {
    connected.value = false
    checkpoints.value = []
    connectionMessage.value = error instanceof Error ? error.message : "连接失败"
  }
}

async function checkCandidateConnection() {
  const state = await api.checkStatus({ ...config })
  connected.value = state.connected
  connectionMessage.value = state.connected ? state.message : "ComfyUI 正在启动..."
  return state.connected
}

async function waitForCandidateComfyui() {
  for (let attempt = 0; attempt < 60; attempt++) {
    if (await checkCandidateConnection()) return true
    await new Promise(resolve => setTimeout(resolve, 500))
  }
  return false
}

async function refreshModels() {
  if (!connected.value) {
    message.info("尚未连接 ComfyUI，请先在「连接设置」完成连接")
    return
  }
  loadingModels.value = true
  try {
    const catalog = await api.models()
    modelCatalog.value = catalog
    connected.value = catalog.connected
    connectionMessage.value = catalog.message
    checkpoints.value = catalog.local_models
      .filter(item => item.kind === "checkpoint")
      .map(item => item.filename)
    if (!form.checkpoint && checkpoints.value.length) form.checkpoint = checkpoints.value[0]
  } catch (error) {
    message.error(error instanceof Error ? error.message : "模型目录加载失败")
  } finally {
    loadingModels.value = false
  }
}

function selectModel(model: ModelItem) {
  if (model.kind !== "checkpoint") {
    message.info("当前只支持选择 checkpoint 用于图片生成")
    return
  }
  form.checkpoint = model.filename
  message.success(`已选择模型：${model.filename}`)
}

async function ensureLocalComfyuiReady() {
  config.api_url = localApiUrl
  notice.value = "正在检查本地 ComfyUI..."
  if (await checkCandidateConnection()) return true

  notice.value = "正在启动本地 ComfyUI..."
  await startComfyui(config.comfyui_path ?? "")
  notice.value = "正在等待 ComfyUI 启动..."
  return waitForCandidateComfyui()
}

// Download is intentionally allowed only after local ComfyUI path is configured.
async function downloadModel(id: string, destination: "remote" | "local" = "local") {
  if (!config.comfyui_path?.trim()) {
    message.warning("请先在连接设置填写模型下载目录（本地 ComfyUI 目录）")
    return
  }

  downloadingModelId.value = id
  try {
    const model = await api.downloadModel(id, destination)
    message.success(
      destination === "remote"
        ? `已在远程设备添加下载任务：${model.name}`
        : `已添加下载任务：${model.name}`,
    )
    await refreshModels()
  } catch (error) {
    message.error(error instanceof Error ? error.message : "模型下载失败")
  } finally {
    downloadingModelId.value = ""
  }
}

// User-triggered test: show one toast plus one status area, no duplicate alert.
async function refreshConnection() {
  notice.value = ""
  noticeType.value = "info"
  if (!validateSettings()) return

  testingConnection.value = true
  try {
    if (config.mode === "local") {
      const ready = await ensureLocalComfyuiReady()
      notice.value = "正在启动并连接本地 ComfyUI..."
      notice.value = ready ? "连接成功" : "ComfyUI 启动超时，请稍后重试"
      if (ready) {
        await api.saveConfig(config)
        message.success("测试连接成功，设置已保存")
        void refreshModels()
      }
      return
    }

    await checkConnection()
    if (connected.value) {
      await api.saveConfig(config)
      message.success("测试连接成功，设置已保存")
      void refreshModels()
    } else {
      message.error(`测试连接失败：${connectionMessage.value}`)
    }
  } finally {
    testingConnection.value = false
  }
}

async function chooseComfyuiDirectory() {
  try {
    let selected: string | null = null
    if (isDesktop()) {
      selected = await selectComfyuiDirectory()
    } else {
      selected = await pickDirectoryViaBrowser()
    }
    if (selected) {
      config.comfyui_path = selected
      clearActionState()
    }
  } catch (error) {
    notice.value = error instanceof Error ? error.message : String(error)
    noticeType.value = "error"
  }
}

async function loadVideoModels() {
  try {
    const models = await api.videoModels()
    motionModels.value = models
    if (!videoForm.motion_model && models.length) {
      videoForm.motion_model = models[0]
    }
  } catch {
    motionModels.value = []
  }
}

async function loadVaeModels() {
  try {
    vaeModels.value = await api.vaeModels()
  } catch {
    vaeModels.value = []
  }
}

function pickDirectoryViaBrowser(): Promise<string | null> {
  return new Promise(resolve => {
    const input = document.createElement("input")
    input.type = "file"
    input.setAttribute("webkitdirectory", "")
    input.style.display = "none"
    document.body.appendChild(input)
    input.onchange = () => {
      const file = input.files?.[0]
      const folder = file?.webkitRelativePath?.split("/")[0] ?? null
      input.remove()
      if (folder) {
        notice.value = "浏览器模式仅能获取目录名称，请在输入框中补充完整路径（如 D:\\ComfyUI）"
      }
      resolve(folder)
    }
    input.oncancel = () => {
      input.remove()
      resolve(null)
    }
    input.click()
  })
}

function redrawTask(task: GenerationTask) {
  const target = task.request.media_type === "video" ? videoForm : form
  Object.assign(target, {
    prompt: task.request.prompt,
    negative_prompt: task.request.negative_prompt,
    checkpoint: task.request.checkpoint,
    media_type: task.request.media_type,
    frames: task.request.frames,
    width: task.request.width,
    height: task.request.height,
    steps: task.request.steps,
    cfg: task.request.cfg,
    seed: task.request.seed,
    sampler: task.request.sampler,
    scheduler: task.request.scheduler,
    batch_size: task.request.batch_size,
  })
  submissionAttempted.value = false
  videoSubmissionAttempted.value = false
  page.value = task.request.media_type === "video" ? "video" : "generate"
}

async function deleteHistoryItem(id: string) {
  try {
    await api.deleteHistory(id)
    history.value = history.value.filter(item => item.id !== id)
    message.success("已删除")
  } catch (error) {
    message.error(error instanceof Error ? error.message : "删除失败")
  }
}

async function openSaveLocation(task: GenerationTask) {
  const location = resolveSaveLocation(task, config)
  if (!location) return
  if (location.kind === "path" && isDesktop()) {
    try {
      await openInExplorer(location.text)
      return
    } catch {
      // 桌面端打开失败时回退到复制路径
    }
  }
  if (location.kind === "url") {
    window.open(location.text, "_blank", "noopener")
    return
  }
  try {
    await navigator.clipboard.writeText(location.text)
    message.success("已复制保存位置")
  } catch {
    message.info(location.text)
  }
}

// Submit a generation task and keep local history in sync.
async function generate() {
  busy.value = true
  notice.value = ""
  noticeType.value = "info"
  submissionAttempted.value = true
  try {
    const task = await api.generate(form)
    currentTask.value = task
    history.value = upsertTask(history.value, task)
    notice.value = `任务已提交：${task.prompt_id}`

    for (let attempt = 0; attempt < 360 && currentTask.value.status !== "completed"; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      currentTask.value = await api.generation(task.id)
      history.value = upsertTask(history.value, currentTask.value)
      if (currentTask.value.status === "failed") break
    }
  } catch (error) {
    noticeType.value = "error"
    notice.value = error instanceof Error ? error.message : "提交失败"
  } finally {
    busy.value = false
  }
}

async function generateVideo() {
  videoBusy.value = true
  videoNotice.value = ""
  videoNoticeType.value = "info"
  videoSubmissionAttempted.value = true
  try {
    const task = await api.generate(videoForm)
    videoTask.value = task
    history.value = upsertTask(history.value, task)
    videoNotice.value = `任务已提交：${task.prompt_id}`

    for (
      let attempt = 0;
      attempt < 720 && videoTask.value.status !== "completed";
      attempt++
    ) {
      await new Promise(resolve => setTimeout(resolve, 1000))
      videoTask.value = await api.generation(task.id)
      history.value = upsertTask(history.value, videoTask.value)
      if (videoTask.value.status === "failed") break
    }
  } catch (error) {
    videoNoticeType.value = "error"
    videoNotice.value = error instanceof Error ? error.message : "提交失败"
  } finally {
    videoBusy.value = false
  }
}

onMounted(async () => {
  startupError.value = ""
  try {
    const desktopError = takeDesktopStartupError()
    if (desktopError) throw new Error(desktopError)
    Object.assign(config, await api.config())
    history.value = await api.history()
    if (config.mode === "remote" && config.api_url.trim()) {
      await checkConnection()
      if (connected.value) {
        await refreshModels()
        await loadVideoModels()
        await loadVaeModels()
      }
    }
  } catch (error) {
    connected.value = false
    startupError.value = error instanceof Error ? error.message : String(error)
    connectionMessage.value = startupError.value
    notice.value = `本地 Agent 不可用：${startupError.value}`
    noticeType.value = "error"
  }
})
</script>

<template>
  <Layout class="app-layout">
    <AppSidebar v-model:page="page" :collapsed="sidebarCollapsed" :connected="connected" />

    <Layout class="app-main-layout">
      <Layout.Header class="app-header">
        <div class="header-left">
          <Button
            type="text"
            class="header-trigger"
            :aria-label="sidebarCollapsed ? '展开菜单' : '收起菜单'"
            @click="sidebarCollapsed = !sidebarCollapsed"
          >
            <MenuUnfoldOutlined v-if="sidebarCollapsed" />
            <MenuFoldOutlined v-else />
          </Button>
          <div class="header-page">
            <strong>{{ pageMeta[page].label }}</strong>
            <span>{{ pageMeta[page].hint }}</span>
          </div>
        </div>

        <Space class="header-actions" :size="8">
          <Tag :color="connected ? 'success' : 'default'">{{ connected ? "已连接" : "未连接" }}</Tag>
          <Button
            v-for="item in quickPages"
            :key="item.value"
            size="small"
            :type="page === item.value ? 'primary' : 'text'"
            @click="page = item.value"
          >
            {{ item.label }}
          </Button>
        </Space>
      </Layout.Header>

      <Layout.Content class="app-content">
        <GenerateView
          v-if="page === 'generate'"
          :form="form"
          :checkpoints="checkpoints"
          :vae-models="vaeModels"
          :current-task="currentTask"
          :can-generate="canGenerate"
          :blocked-reason="generationBlockedReason"
          :busy="busy"
          :notice="notice"
          :notice-type="noticeType"
          :submission-attempted="submissionAttempted"
          @go-models="page = 'models'"
          @generate="generate"
        />
        <VideoView
          v-else-if="page === 'video'"
          :form="videoForm"
          :checkpoints="checkpoints"
          :vae-models="vaeModels"
          :current-task="videoTask"
          :can-generate="canGenerateVideo"
          :blocked-reason="videoBlockedReason"
          :busy="videoBusy"
          :notice="videoNotice"
          :notice-type="videoNoticeType"
          :submission-attempted="videoSubmissionAttempted"
          :motion-models="motionModels"
          @go-models="page = 'models'"
          @generate="generateVideo"
        />
        <ModelsView
          v-else-if="page === 'models'"
          :config="config"
          :connected="connected"
          :catalog="modelCatalog"
          :selected-checkpoint="form.checkpoint"
          :loading="loadingModels"
          :downloading-id="downloadingModelId"
          @refresh="refreshModels"
          @select="selectModel"
          @download="downloadModel"
        />
        <HistoryView
          v-else-if="page === 'history'"
          :history="history"
          :config="config"
          @redraw="redrawTask"
          @remove="deleteHistoryItem"
          @open-location="openSaveLocation"
        />
        <SettingsView
          v-else
          :config="config"
          :connected="connected"
          :connection-message="connectionMessage"
          :busy="busy"
          :testing-connection="testingConnection"
          :notice="notice"
          :notice-type="noticeType"
          :settings-error="settingsError"
          @clear="clearActionState"
          @choose-directory="chooseComfyuiDirectory"
          @refresh="refreshConnection"
        />
      </Layout.Content>
    </Layout>
  </Layout>
</template>
