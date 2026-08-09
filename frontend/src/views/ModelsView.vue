<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Alert, Button, Card, Checkbox, Col, Empty, Input, Modal, Pagination, Row, Segmented, Select, Space, Spin, Tag, Tooltip } from "ant-design-vue"
import {
  CloudDownloadOutlined,
  LinkOutlined,
  ReloadOutlined,
} from "@ant-design/icons-vue"
import {
  proxiedImageUrl,
  type Config,
  type ContentTag,
  type CreationType,
  type ModelCapabilityUpdate,
  type ModelCatalogResponse,
  type ModelItem,
} from "../lib/api"
import { contentTagLabels, creationTypeLabels } from "../lib/modelCapabilities"

const props = defineProps<{
  config: Config
  connected: boolean
  catalog: ModelCatalogResponse
  catalogLoaded: boolean
  loading: boolean
  downloadingKey: string
  downloadingModels: ModelItem[]
  enablingManager: boolean
}>()

const emit = defineEmits<{
  refresh: []
  select: [model: ModelItem]
  download: [id: string, destination: "remote" | "local"]
  enableManager: []
  openManager: []
  saveCapabilities: [profile: ModelCapabilityUpdate]
}>()

const editingModel = ref<ModelItem | null>(null)
const editingCapabilities = ref<CreationType[]>([])
const editingContentTags = ref<ContentTag[]>(["general"])
const editingDescription = ref("")
const capabilityOptions = Object.entries(creationTypeLabels).map(([value, label]) => ({
  value: value as CreationType,
  label,
}))
const contentTagOptions = Object.entries(contentTagLabels).map(([value, label]) => ({
  value: value as ContentTag,
  label,
}))

function openCapabilitySettings(model: ModelItem) {
  editingModel.value = model
  editingCapabilities.value = [...model.capability_profile.capabilities]
  editingContentTags.value = [...model.capability_profile.content_tags]
  editingDescription.value = model.capability_profile.description_zh
}

function saveCapabilitySettings() {
  if (!editingModel.value || !editingContentTags.value.length) return
  const requiredInputs: ModelCapabilityUpdate["required_inputs"] = {}
  const requiredComponents: ModelCapabilityUpdate["required_components"] = {}
  const workflowFamily: ModelCapabilityUpdate["workflow_family"] = {}
  for (const capability of editingCapabilities.value) {
    if (capability === "image_to_image" || capability === "image_to_video") {
      requiredInputs[capability] = ["reference_image"]
    } else if (capability === "video_to_video") {
      requiredInputs[capability] = ["reference_video"]
    }
    if (capability === "text_to_video") {
      requiredComponents[capability] = ["motion_model"]
      workflowFamily[capability] = "animatediff"
    } else if (capability === "image_to_video" || capability === "video_to_video") {
      requiredComponents[capability] = ["text_encoder", "vae"]
      workflowFamily[capability] = "wan_video"
    } else {
      workflowFamily[capability] = "standard_checkpoint"
    }
  }
  emit("saveCapabilities", {
    filename: editingModel.value.filename,
    capabilities: [...editingCapabilities.value],
    required_inputs: requiredInputs,
    required_components: requiredComponents,
    workflow_family: workflowFamily,
    content_tags: [...editingContentTags.value],
    description_zh: editingDescription.value.trim(),
    recommended_params: editingModel.value.capability_profile.recommended_params,
    confirmed: editingCapabilities.value.length > 0,
  })
  editingModel.value = null
}

const localModelPath = computed(() =>
  props.config.local_model_path || (props.config.mode === "local" ? props.config.comfyui_path : null),
)
const canDownloadLocal = computed(() => Boolean(localModelPath.value))
const isModelDownloading = (item: ModelItem) =>
  props.downloadingModels.some(model => model.id === item.id)
const downloadDisabledReason = computed(() => {
  if (!localModelPath.value) return "请先在连接设置填写本地模型目录"
  return ""
})

const kindFilter = ref<"all" | ModelItem["kind"]>("all")
const remoteKindFilter = ref<"all" | ModelItem["kind"]>("all")
const localKindFilter = ref<"all" | ModelItem["kind"]>("all")
const usageFilter = ref<"all" | ModelItem["usage"]>("all")
const modelSourceFilter = ref<"available" | "local" | "remote">("available")
const onlinePage = ref(1)
const onlinePageSize = 12
const modelSourceOptions = [
  { label: "可用模型", value: "available" },
  { label: "本地模型", value: "local" },
  { label: "远程模型", value: "remote" },
]
const kindFilterOptions = [
  { label: "全部", value: "all" },
  { label: "Checkpoint", value: "checkpoint" },
  { label: "LoRA", value: "lora" },
  { label: "ControlNet", value: "controlnet" },
  { label: "VAE", value: "vae" },
  { label: "其他", value: "other" },
]
const usageFilterOptions = [
  { label: "全部用途", value: "all" },
  { label: "图片模型", value: "image" },
  { label: "视频模型", value: "video" },
]
const filteredLocalModels = computed(() =>
  props.catalog.local_models.filter(
    item =>
      (localKindFilter.value === "all" || item.kind === localKindFilter.value) &&
      (usageFilter.value === "all" || item.usage === usageFilter.value),
  ),
)
const filteredRemoteModels = computed(() =>
  props.catalog.remote_models.filter(
    item =>
      (remoteKindFilter.value === "all" || item.kind === remoteKindFilter.value) &&
      (usageFilter.value === "all" || item.usage === usageFilter.value),
  ),
)
const filteredOnlineModels = computed(() =>
  props.catalog.online_models.filter(
    item =>
      (kindFilter.value === "all" || item.kind === kindFilter.value) &&
      (usageFilter.value === "all" || item.usage === usageFilter.value),
  ),
)
const pagedOnlineModels = computed(() =>
  filteredOnlineModels.value.slice(
    (onlinePage.value - 1) * onlinePageSize,
    onlinePage.value * onlinePageSize,
  ),
)
watch(kindFilter, () => {
  onlinePage.value = 1
})
watch(usageFilter, () => {
  onlinePage.value = 1
})

function kindText(kind: ModelItem["kind"]) {
  return {
    checkpoint: "Checkpoint",
    lora: "LoRA",
    controlnet: "ControlNet",
    vae: "VAE",
    other: "其他",
  }[kind]
}

function usageMeta(usage: ModelItem["usage"]) {
  return usage === "video"
    ? { text: "视频", color: "purple" }
    : { text: "图片", color: "blue" }
}

function sourceText(source: ModelItem["source"]) {
  return source === "local"
    ? "本地文件"
    : source === "comfyui"
      ? props.config.mode === "local"
        ? "ComfyUI 可用"
        : "远程可用"
      : "在线模型"
}

const availableModelTitle = computed(() =>
  props.config.mode === "local" ? "ComfyUI 可用模型" : "远程可用模型",
)
</script>

<template>
  <div class="page-workspace page-scroll">

  <Modal
    :open="Boolean(editingModel)"
    title="模型能力设置"
    :footer="null"
    @cancel="editingModel = null"
  >
    <Space direction="vertical" size="middle" style="width: 100%">
      <span class="field-help">请选择该模型与当前内置工作流兼容的用途。</span>
      <Checkbox.Group v-model:value="editingCapabilities">
        <Space direction="vertical">
          <Checkbox v-for="option in capabilityOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </Checkbox>
        </Space>
      </Checkbox.Group>
      <div>
        <div class="field-label">擅长内容</div>
        <Select
          v-model:value="editingContentTags"
          mode="multiple"
          :options="contentTagOptions"
          placeholder="至少选择一个内容标签"
          style="width: 100%"
        />
      </div>
      <Input.TextArea v-model:value="editingDescription" :rows="3" placeholder="中文用途说明" />
      <Space style="justify-content: flex-end; width: 100%">
        <Button @click="editingModel = null">取消</Button>
        <Button
          data-testid="save-capabilities"
          type="primary"
          :disabled="!editingContentTags.length"
          @click="saveCapabilitySettings"
        >
          保存
        </Button>
      </Space>
    </Space>
  </Modal>

  <Card :bordered="false" class="model-toolbar">
    <div class="model-toolbar-content">
      <Space :size="8" wrap>
        <Button :loading="loading" :disabled="loading" @click="emit('refresh')">
          <template #icon><ReloadOutlined /></template>
          刷新模型
        </Button>
        <Tag :color="catalog.manager_available ? 'success' : 'default'">
          {{ catalog.manager_available ? 'Manager 已启用' : 'Manager 未启用' }}
        </Tag>
        <Button
          v-if="connected && catalog.manager_available"
          type="primary"
          @click="emit('openManager')"
        >
          打开 ComfyUI 模型库
        </Button>
        <Button
          v-else-if="connected && config.mode === 'local'"
          type="primary"
          :loading="enablingManager"
          @click="emit('enableManager')"
        >
          一键启用 Manager
        </Button>
      </Space>
      <div class="model-toolbar-status">
        <span v-if="connected" class="field-help">{{ catalog.message }}</span>
        <div class="model-toolbar-stats">
          <span class="model-stat-item">{{ config.mode === 'local' ? 'ComfyUI 可用' : '远程可用' }}：{{ catalog.remote_models.length }}</span>
          <span class="model-stat-item">本地目录：{{ catalog.local_models.length }}</span>
          <span class="model-stat-item">在线模型：{{ catalog.online_models.length }}</span>
        </div>
      </div>
    </div>
  </Card>

  <Alert
    v-if="downloadingModels.length"
    class="model-section"
    type="info"
    show-icon
    :message="`正在下载：${downloadingModels.map(item => item.name).join('、')}`"
    description="下载任务串行执行，完成一个才会开始下一个；正在下载的模型其下载按钮已禁用，其他模型仍可添加任务。"
  />

  <Alert
    v-if="!connected"
    type="info"
    show-icon
    message="尚未连接 ComfyUI"
    description="模型管理需要先建立 ComfyUI 连接。请在「连接设置」页面完成连接，连接成功后可在此浏览、选择与下载模型。"
  />
  <Alert
    v-else-if="catalogLoaded && !catalog.connected && !loading"
    type="warning"
    show-icon
    message="模型目录加载失败"
    :description="catalog.message || '请点击「刷新模型」重试。'"
  />

  <Card v-else-if="!catalogLoaded" :bordered="false" class="model-section model-loading-card">
    <div class="model-loading">
      <Spin />
      <span>正在加载模型目录，请稍候...</span>
    </div>
  </Card>

  <template v-else>
    <Segmented
      v-model:value="modelSourceFilter"
      :options="modelSourceOptions"
      block
      class="model-source-switcher"
    />

    <Alert
      v-if="config.mode !== 'local' || !config.comfyui_path"
      class="model-section"
      type="warning"
      show-icon
      message="远程连接说明"
      description="远程模式下，只有远程 ComfyUI 可用模型能直接用于生成。本地目录模型只是本机文件，不能直接被远程 ComfyUI 调用。"
    />

    <Card v-if="modelSourceFilter === 'available'" :bordered="false" class="model-section">
      <template #title>
        <Space class="model-section-title" wrap>
          <span>{{ availableModelTitle }}</span>
          <Segmented v-model:value="usageFilter" :options="usageFilterOptions" size="small" />
          <Segmented v-model:value="remoteKindFilter" :options="kindFilterOptions" size="small" />
        </Space>
      </template>
      <Empty
        v-if="!filteredRemoteModels.length"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        :description="`当前筛选没有${availableModelTitle}。`"
      />
      <Row v-else :gutter="[12, 12]" class="model-list-row">
        <Col v-for="item in filteredRemoteModels" :key="item.id" :xs="24">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span :title="item.name">{{ item.name }}</span>
                <Tag :color="usageMeta(item.usage).color">{{ usageMeta(item.usage).text }}</Tag>
                <Tag>{{ kindText(item.kind) }}</Tag>
                <Tag v-if="item.kind === 'checkpoint'" :color="item.capability_profile.confirmed ? 'success' : 'warning'">
                  {{ item.capability_profile.confirmed ? '能力已确认' : '能力待确认' }}
                </Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="proxiedImageUrl(item.preview_url)" :alt="item.name" class="model-preview-image" />
              <div v-else class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ item.source === "comfyui" ? "ComfyUI 可用" : "本地文件" }}</span>
              </div>
              <div class="model-file" :title="item.filename">{{ item.filename }}</div>
              <div class="model-file" :title="item.path || '未配置本地路径'">{{ item.path || "未配置本地路径" }}</div>
              <Space>
                <Button
                  :disabled="item.kind !== 'checkpoint' && item.usage !== 'video' && item.kind !== 'vae'"
                  @click="emit('select', item)"
                >
                  应用
                </Button>
                <Button v-if="item.kind === 'checkpoint'" @click="openCapabilitySettings(item)">
                  能力设置
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card v-if="modelSourceFilter === 'local'" :bordered="false" class="model-section">
      <template #title>
        <Space class="model-section-title" wrap>
          <span>本地目录模型</span>
          <Segmented v-model:value="localKindFilter" :options="kindFilterOptions" size="small" />
        </Space>
      </template>
      <Alert
        v-if="config.mode === 'remote'"
        class="model-section"
        type="warning"
        show-icon
        message="远程模式不能使用本地模型"
        description="本地模型只是本机文件，远程 ComfyUI 无法加载。如需使用本地模型绘制，请到连接设置切换到本地 ComfyUI 模式，再用「测试连接」连接。"
      />
      <Empty
        v-if="!filteredLocalModels.length"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        description="未发现本地真实模型文件，请在连接设置中填写本地模型目录。"
      />
      <Row v-else :gutter="[12, 12]" class="model-list-row">
        <Col v-for="item in filteredLocalModels" :key="item.id" :xs="24">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span :title="item.name">{{ item.name }}</span>
                <Tag :color="usageMeta(item.usage).color">{{ usageMeta(item.usage).text }}</Tag>
                <Tag>{{ kindText(item.kind) }}</Tag>
                <Tag v-if="item.kind === 'checkpoint'" :color="item.capability_profile.confirmed ? 'success' : 'warning'">
                  {{ item.capability_profile.confirmed ? '能力已确认' : '能力待确认' }}
                </Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="proxiedImageUrl(item.preview_url)" :alt="item.name" class="model-preview-image" />
              <div v-else class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ sourceText(item.source) }}</span>
              </div>
              <div class="model-file" :title="item.filename">{{ item.filename }}</div>
              <div class="model-file" :title="item.path || '未配置本地路径'">{{ item.path || "未配置本地路径" }}</div>
              <Space>
                <Tag>本机文件</Tag>
                <Tooltip :title="config.mode === 'remote' ? '远程模式不能使用本地模型，请切换到本地模式后使用' : ''">
                  <Button
                    :disabled="(item.kind !== 'checkpoint' && item.usage !== 'video' && item.kind !== 'vae') || config.mode === 'remote'"
                    @click="emit('select', item)"
                  >
                    应用
                  </Button>
                </Tooltip>
                <Button v-if="item.kind === 'checkpoint'" @click="openCapabilitySettings(item)">
                  能力设置
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card
      v-if="modelSourceFilter === 'remote'"
      title="在线模型库"
      :bordered="false"
      class="model-section"
    >
      <Alert
        v-if="!catalog.manager_available"
        type="info"
        show-icon
        message="在线模型库不可用"
        :description="`当前 ComfyUI 未安装或未启用 ComfyUI Manager，仅展示${availableModelTitle}和本地目录模型。启用后即可浏览在线模型库。`"
      />
      <template v-else>
        <Alert
          class="model-section"
          type="info"
          show-icon
          message="模型下载说明"
          description="下载到远程设备：模型将安装至远程 ComfyUI，刷新后可在生成页选择使用。下载到本地路径：文件仅保存至本地目录，远程生成不会调用；本地 ComfyUI 模式下下载的模型可直接用于生成。"
        />
        <Space class="model-toolbar-content model-filter-row">
          <Segmented v-model:value="usageFilter" :options="usageFilterOptions" />
          <Segmented v-model:value="kindFilter" :options="kindFilterOptions" />
        </Space>
        <Empty
          v-if="!filteredOnlineModels.length"
          :image="Empty.PRESENTED_IMAGE_SIMPLE"
          description="当前分类没有可下载模型"
        />
        <Row v-else :gutter="[12, 12]" class="model-section model-list-row">
        <Col v-for="item in pagedOnlineModels" :key="item.id" :xs="24">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span :title="item.name">{{ item.name }}</span>
                <Tag :color="usageMeta(item.usage).color">{{ usageMeta(item.usage).text }}</Tag>
                <Tag>{{ kindText(item.kind) }}</Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="proxiedImageUrl(item.preview_url)" :alt="item.name" class="model-preview-image" />
              <div v-else class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ item.size_label || "Manager 模型库" }}</span>
              </div>
              <p class="model-desc" :title="item.description">{{ item.description }}</p>
              <div class="model-file" :title="item.filename">{{ item.filename }}</div>
              <Space>
                <Tag :color="item.installed ? 'success' : 'default'">
                  {{ item.installed ? (config.mode === 'local' ? "已在 ComfyUI 可用" : "已在远程可用") : "可安装" }}
                </Tag>
                <Button
                  v-if="item.reference_url"
                  :href="item.reference_url"
                  target="_blank"
                  rel="noopener"
                >
                  <template #icon><LinkOutlined /></template>
                  详情
                </Button>
                <Button
                  v-if="item.installed"
                  :disabled="item.kind !== 'checkpoint' && item.usage !== 'video' && item.kind !== 'vae'"
                  @click="emit('select', item)"
                >
                  应用
                </Button>
                <template v-else>
                  <Button
                    v-if="config.mode === 'remote'"
                    :loading="downloadingKey === item.id + '|remote'"
                    :disabled="isModelDownloading(item)"
                    @click="emit('download', item.id, 'remote')"
                  >
                    <template #icon><CloudDownloadOutlined /></template>
                    下载到远程
                  </Button>
                  <Tooltip :title="!canDownloadLocal ? downloadDisabledReason : ''">
                    <Button
                      type="primary"
                      :disabled="isModelDownloading(item) || !canDownloadLocal"
                      :loading="downloadingKey === item.id + '|local'"
                      @click="emit('download', item.id, 'local')"
                    >
                      <template #icon><CloudDownloadOutlined /></template>
                      {{ config.mode === 'local' ? '下载模型' : '下载到本地' }}
                    </Button>
                  </Tooltip>
                </template>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
      <Pagination
        v-if="filteredOnlineModels.length > onlinePageSize"
        v-model:current="onlinePage"
        :page-size="onlinePageSize"
        :total="filteredOnlineModels.length"
        :show-size-changer="false"
        class="model-pagination"
      />
      </template>
    </Card>
  </template>
  </div>
</template>
