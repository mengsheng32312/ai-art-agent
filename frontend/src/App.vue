<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue"
import { Button, ConfigProvider, Layout, message, Space, Tag } from "ant-design-vue"
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons-vue"
import AppSidebar from "./components/AppSidebar.vue"
import { antTheme } from "./styles/theme"
import {
  isDesktop,
  openInExplorer,
  prepareDesktopAgent,
  recordDesktopStartupError,
  selectComfyuiDirectory,
  selectDirectory,
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
import DownloadsView from "./views/DownloadsView.vue"
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
const loraModels = ref<string[]>([])
const controlnetModels = ref<string[]>([])
const vaeModels = ref<string[]>([])
const modelCatalog = ref<ModelCatalogResponse>({
  connected: false,
  manager_available: false,
  message: "请先连接 ComfyUI",
  remote_models: [],
  local_models: [],
  online_models: [],
})
const history = ref<GenerationTask[]>([])
const currentTask = ref<GenerationTask | null>(null)
const busy = ref(false)
const testingConnection = ref(false)
const loadingModels = ref(false)
const downloadingModelKey = ref("")
const remoteDownloadingModels = ref<ModelItem[]>([])
const catalogLoaded = ref(false)
const notice = ref("")
const noticeType = ref<"info" | "success" | "error">("info")
const submissionAttempted = ref(false)
const startupError = ref("")
const localApiUrl = "http://127.0.0.1:8188"

// 图片生成只允许图片用途的 checkpoint，视频模型（如 Wan）不会出现在图片页。
const imageCheckpoints = computed(() =>
  modelCatalog.value.remote_models
    .filter(item => item.kind === "checkpoint" && item.usage === "image")
    .map(item => item.filename),
)

const pageMeta: Record<Page, { label: string; hint: string }> = {
  generate: { label: "图片生成", hint: "参数与预览" },
  video: { label: "视频生成", hint: "AnimateDiff" },
  models: { label: "模型管理", hint: "本地与在线模型" },
  downloads: { label: "下载队列", hint: "远程下载任务" },
  history: { label: "历史记录", hint: "结果与工作流" },
  settings: { label: "连接设置", hint: "ComfyUI" },
}

const config = reactive<Config>({
  mode: "local",
  comfyui_path: null,
  local_model_path: null,
  api_url: "http://127.0.0.1:8188",
})

const form = reactive(createDefaultGenerationRequest())
const canGenerate = computed(() => canSubmitGeneration(form, connected.value, busy.value))
const generationBlockedReason = computed(() =>
  getGenerationBlockedReason(form, connected.value, busy.value, imageCheckpoints.value),
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
    catalogLoaded.value = true
    connected.value = catalog.connected
    connectionMessage.value = catalog.message
    checkpoints.value = catalog.remote_models
      .filter(item => item.kind === "checkpoint")
      .map(item => item.filename)
    if (!form.checkpoint && imageCheckpoints.value.length) {
      form.checkpoint = imageCheckpoints.value[0]
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : "模型目录加载失败")
    catalogLoaded.value = true
  } finally {
    loadingModels.value = false
  }
}

watch(page, value => {
  if (value === "models" && connected.value && !catalogLoaded.value) {
    void refreshModels()
  }
})

watch(page, value => {
  if (
    value === "generate" &&
    form.checkpoint &&
    !imageCheckpoints.value.includes(form.checkpoint)
  ) {
    form.checkpoint = imageCheckpoints.value[0] ?? ""
  }
})

function selectModel(model: ModelItem) {
  if (model.source === "local" && config.mode === "remote") {
    message.info("本地目录模型不能直接用于远程生成，请先安装到远程 ComfyUI")
    return
  }
  if (model.usage === "video") {
    if (videoForm.video_mode === "i2v" || videoForm.video_mode === "v2v") {
      videoForm.checkpoint = model.filename
    } else {
      videoForm.motion_model = model.filename
      if (!motionModels.value.includes(model.filename)) {
        motionModels.value.push(model.filename)
      }
    }
    page.value = "video"
    message.success(`已选择视频模型：${model.name}`)
    return
  }
  if (model.kind === "vae") {
    form.vae = model.filename
    videoForm.vae = model.filename
    if (!vaeModels.value.includes(model.filename)) {
      vaeModels.value.push(model.filename)
    }
    page.value = "generate"
    message.success(`已选择 VAE 模型：${model.name}`)
    return
  }
  if (model.kind !== "checkpoint") {
    message.info("当前只支持选择 checkpoint 用于图片生成")
    return
  }
  form.checkpoint = model.filename
  page.value = "generate"
  message.success(`已选择模型：${model.name}`)
}

async function ensureLocalComfyuiReady() {
  config.api_url = localApiUrl
  connectionMessage.value = "正在检查本地 ComfyUI..."
  if (await checkCandidateConnection()) return true

  connectionMessage.value = "正在启动本地 ComfyUI..."
  await startComfyui(config.comfyui_path ?? "")
  connectionMessage.value = "正在等待 ComfyUI 启动..."
  return waitForCandidateComfyui()
}

// 本地下载需要明确的模型目录；本地模式可回退到 ComfyUI 安装目录。
async function downloadModel(id: string, destination: "remote" | "local" = "local") {
  const localModelPath = config.local_model_path?.trim() || (
    config.mode === "local" ? config.comfyui_path?.trim() : ""
  )
  if (destination === "local" && !localModelPath) {
    message.warning("请先在连接设置填写本地模型目录")
    return
  }

  downloadingModelKey.value = `${id}|${destination}`
  try {
    const model = await api.downloadModel(id, destination)
    if (destination === "remote") {
      message.success(`已添加到下载队列：${model.name}`)
      if (!remoteDownloadingModels.value.some(item => item.id === model.id)) {
        remoteDownloadingModels.value.push(model)
      }
      await waitForRemoteDownload(model)
      remoteDownloadingModels.value = remoteDownloadingModels.value.filter(
        item => item.id !== model.id,
      )
    } else {
      message.success(`已添加到下载队列：${model.name}`)
      await refreshModels()
    }
  } catch (error) {
    message.error(error instanceof Error ? error.message : "模型下载失败")
  } finally {
    downloadingModelKey.value = ""
  }
}

// 远程下载由 ComfyUI Manager 队列执行，轮询队列状态与远程模型列表确认完成。
async function waitForRemoteDownload(model: ModelItem) {
  let failures = 0
  for (;;) {
    await new Promise(resolve => setTimeout(resolve, 5000))
    try {
      const status = await api.managerStatus()
      failures = 0
      if (!status.is_processing) {
        await refreshModels()
        const installed = modelCatalog.value.remote_models.some(
          item => item.filename === model.filename,
        )
        if (installed) {
          message.success(`模型下载完成：${model.name}`)
        } else {
          message.warning(
            `下载任务已结束但未检测到模型文件，请查看远程 ComfyUI Manager 日志`,
          )
        }
        return
      }
    } catch {
      failures += 1
      if (failures >= 6) {
        message.info("暂时无法查询远程下载状态，稍后刷新模型列表确认结果")
        return
      }
    }
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
      connectionMessage.value = ready ? "连接正常" : "ComfyUI 启动超时，请稍后重试"
      if (ready) {
        await api.saveConfig(config)
        message.success("测试连接成功，设置已保存")
        void loadVideoModels()
        void loadVaeModels()
        void loadLoraModels()
        void loadControlnetModels()
      }
      return
    }

    try {
      const state = await api.checkStatus({ ...config })
      connected.value = state.connected
      connectionMessage.value = state.message
      if (connected.value) {
        checkpoints.value = await api.checkpoints()
        if (!form.checkpoint && imageCheckpoints.value.length) {
          form.checkpoint = imageCheckpoints.value[0]
        }
        await api.saveConfig(config)
        message.success("测试连接成功，设置已保存")
        void loadVideoModels()
        void loadVaeModels()
        void loadLoraModels()
        void loadControlnetModels()
      } else {
        message.error(`测试连接失败：${state.message}`)
      }
    } catch (error) {
      connected.value = false
      checkpoints.value = []
      connectionMessage.value = error instanceof Error ? error.message : "连接失败"
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
      notice.value = "浏览器模式不能读取完整文件夹路径，请直接在输入框中填写完整目录"
      noticeType.value = "info"
      return
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

async function chooseLocalModelDirectory() {
  try {
    if (!isDesktop()) {
      notice.value = "浏览器模式不能读取完整文件夹路径，请直接在输入框中填写完整目录"
      noticeType.value = "info"
      return
    }
    const selected = await selectDirectory()
    if (selected) {
      config.local_model_path = selected
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

async function loadLoraModels() {
  try {
    loraModels.value = await api.loraModels()
  } catch {
    loraModels.value = []
  }
}

async function loadControlnetModels() {
  try {
    controlnetModels.value = await api.controlnetModels()
  } catch {
    controlnetModels.value = []
  }
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
    await prepareDesktopAgent().catch(recordDesktopStartupError)
    const desktopError = takeDesktopStartupError()
    if (desktopError) throw new Error(desktopError)
    Object.assign(config, await api.config())
    history.value = await api.history()
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
  <ConfigProvider :theme="antTheme">
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
          </Space>
        </Layout.Header>

        <Layout.Content class="app-content">
          <GenerateView
            v-if="page === 'generate'"
            :form="form"
            :checkpoints="imageCheckpoints"
            :lora-models="loraModels"
            :controlnet-models="controlnetModels"
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
            :lora-models="loraModels"
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
            :catalog-loaded="catalogLoaded"
            :loading="loadingModels"
            :downloading-key="downloadingModelKey"
            :downloading-models="remoteDownloadingModels"
            @refresh="refreshModels"
            @select="selectModel"
            @download="downloadModel"
          />
          <DownloadsView
            v-else-if="page === 'downloads'"
            :downloading-models="remoteDownloadingModels"
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
            @choose-model-directory="chooseLocalModelDirectory"
            @refresh="refreshConnection"
          />
        </Layout.Content>
      </Layout>
    </Layout>
  </ConfigProvider>
</template>
