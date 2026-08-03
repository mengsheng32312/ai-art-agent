<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { Button, Layout, message } from "ant-design-vue"
import { MenuFoldOutlined, MenuUnfoldOutlined } from "@ant-design/icons-vue"
import AppSidebar from "./components/AppSidebar.vue"
import { api, type Config, type GenerationTask, type ModelCatalogResponse, type ModelItem } from "./lib/api"
import {
  canSubmitGeneration,
  createDefaultGenerationRequest,
  getGenerationBlockedReason,
  upsertTask,
} from "./stores/generation"
import type { Page } from "./types"
import GenerateView from "./views/GenerateView.vue"
import HistoryView from "./views/HistoryView.vue"
import ModelsView from "./views/ModelsView.vue"
import SettingsView from "./views/SettingsView.vue"

type SettingsAction = "test" | "save"

const page = ref<Page>("generate")
const sidebarCollapsed = ref(false)
const connected = ref(false)
const connectionMessage = ref("尚未连接")
const settingsError = ref("")
const checkpoints = ref<string[]>([])
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

function clearActionState() {
  settingsError.value = ""
  notice.value = ""
}

function validateSettings(action: SettingsAction) {
  settingsError.value = ""
  if (config.mode === "local" && !config.comfyui_path?.trim()) {
    const actionName = action === "test" ? "测试连接" : "保存设置"
    settingsError.value = `${actionName}失败：请选择 ComfyUI 安装目录`
    connected.value = false
    message.warning(settingsError.value)
    return false
  }
  if (config.mode === "remote" && !config.api_url.trim()) {
    const actionName = action === "test" ? "测试连接" : "保存设置"
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

async function refreshModels() {
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

// Download is intentionally allowed only after local ComfyUI path is configured.
async function downloadModel(id: string) {
  if (config.mode !== "local" || !config.comfyui_path?.trim()) {
    message.warning("请先在连接设置选择本地 ComfyUI 目录")
    return
  }

  downloadingModelId.value = id
  try {
    const model = await api.downloadModel(id)
    message.success(`已添加下载任务：${model.name}`)
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
  if (!validateSettings("test")) return

  testingConnection.value = true
  try {
    await checkConnection()
    if (connected.value) {
      message.success("测试连接成功")
      await refreshModels()
    } else {
      message.error(`测试连接失败：${connectionMessage.value}`)
    }
  } finally {
    testingConnection.value = false
  }
}

// Save settings only after validating the active connection mode.
async function saveSettings() {
  notice.value = ""
  if (!validateSettings("save")) return

  busy.value = true
  try {
    await api.saveConfig(config)
    notice.value = "设置已保存"
    message.success("设置已保存")
    await checkConnection()
    await refreshModels()
  } catch (error) {
    notice.value = error instanceof Error ? error.message : "保存失败"
  } finally {
    busy.value = false
  }
}

// Submit a generation task and keep local history in sync.
async function generate() {
  busy.value = true
  notice.value = ""
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
    notice.value = error instanceof Error ? error.message : "提交失败"
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  Object.assign(config, await api.config())
  history.value = await api.history()
  await refreshModels()
  if (config.mode === "remote" && config.api_url.trim()) await checkConnection()
})
</script>

<template>
  <Layout class="app-layout">
    <AppSidebar v-model:page="page" :collapsed="sidebarCollapsed" :connected="connected" />

    <Layout class="app-main-layout">
      <Layout.Header class="app-header">
        <Button
          type="text"
          class="header-trigger"
          :aria-label="sidebarCollapsed ? '展开菜单' : '收起菜单'"
          @click="sidebarCollapsed = !sidebarCollapsed"
        >
          <MenuUnfoldOutlined v-if="sidebarCollapsed" />
          <MenuFoldOutlined v-else />
        </Button>
      </Layout.Header>

      <Layout.Content class="app-content">
        <GenerateView
          v-if="page === 'generate'"
          :form="form"
          :checkpoints="checkpoints"
          :current-task="currentTask"
          :can-generate="canGenerate"
          :blocked-reason="generationBlockedReason"
          :busy="busy"
          :notice="notice"
          @go-models="page = 'models'"
          @generate="generate"
        />
        <ModelsView
          v-else-if="page === 'models'"
          :config="config"
          :catalog="modelCatalog"
          :selected-checkpoint="form.checkpoint"
          :loading="loadingModels"
          :downloading-id="downloadingModelId"
          @refresh="refreshModels"
          @select="selectModel"
          @download="downloadModel"
        />
        <HistoryView v-else-if="page === 'history'" :history="history" />
        <SettingsView
          v-else
          :config="config"
          :connected="connected"
          :connection-message="connectionMessage"
          :busy="busy"
          :testing-connection="testingConnection"
          :notice="notice"
          :settings-error="settingsError"
          @clear="clearActionState"
          @refresh="refreshConnection"
          @save="saveSettings"
        />
      </Layout.Content>
    </Layout>
  </Layout>
</template>
