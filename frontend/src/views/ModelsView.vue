<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Alert, Button, Card, Col, Empty, Pagination, Row, Segmented, Space, Statistic, Tag, Tooltip } from "ant-design-vue"
import { CheckOutlined, CloudDownloadOutlined, ReloadOutlined } from "@ant-design/icons-vue"
import { proxiedImageUrl, type Config, type ModelCatalogResponse, type ModelItem } from "../lib/api"

const props = defineProps<{
  config: Config
  connected: boolean
  catalog: ModelCatalogResponse
  selectedCheckpoint: string
  loading: boolean
  downloadingId: string
}>()

const emit = defineEmits<{
  refresh: []
  select: [model: ModelItem]
  download: [id: string, destination: "remote" | "local"]
}>()

const canDownloadLocal = computed(() => Boolean(props.config.comfyui_path))
const downloadDisabledReason = computed(() => {
  if (!props.config.comfyui_path) return "请先在连接设置填写本地模型目录"
  return ""
})

const kindFilter = ref<"all" | ModelItem["kind"]>("all")
const remoteKindFilter = ref<"all" | ModelItem["kind"]>("all")
const localKindFilter = ref<"all" | ModelItem["kind"]>("all")
const usageFilter = ref<"all" | ModelItem["usage"]>("all")
const downloadTarget = ref<"remote" | "local">("local")
const onlinePage = ref(1)
const onlinePageSize = 12
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
  return source === "local" ? "本地文件" : source === "comfyui" ? "远程可用" : "在线模型"
}
</script>

<template>
  <div class="page-workspace page-scroll">

  <Card :bordered="false" class="model-toolbar">
    <div class="model-toolbar-content">
      <Button :loading="loading" @click="emit('refresh')">
        <template #icon><ReloadOutlined /></template>
        刷新模型
      </Button>
      <div class="model-toolbar-status">
        <span v-if="connected" class="field-help">{{ catalog.message }}</span>
        <div class="model-toolbar-stats">
          <Statistic title="远程可用" :value="catalog.remote_models.length" />
          <Statistic title="本地目录" :value="catalog.local_models.length" />
          <Statistic title="在线模型" :value="catalog.online_models.length" />
        </div>
      </div>
    </div>
  </Card>

  <Alert
    v-if="!connected"
    type="info"
    show-icon
    message="尚未连接 ComfyUI"
    description="模型管理需要先建立 ComfyUI 连接。请在「连接设置」页面完成连接，连接成功后可在此浏览、选择与下载模型。"
  />
  <Alert
    v-else-if="!catalog.connected"
    type="warning"
    show-icon
    message="模型目录加载失败"
    :description="catalog.message || '请点击「刷新模型」重试。'"
  />

  <template v-else>
    <Alert
      v-if="config.mode !== 'local' || !config.comfyui_path"
      class="model-section"
      type="warning"
      show-icon
      message="远程连接说明"
      description="远程模式下，只有远程 ComfyUI 可用模型能直接用于生成。本地目录模型只是本机文件，不能直接被远程 ComfyUI 调用。"
    />

    <Card :bordered="false" class="model-section">
      <template #title>
        <Space class="model-section-title" wrap>
          <span>远程可用模型</span>
          <Segmented v-model:value="usageFilter" :options="usageFilterOptions" size="small" />
          <Segmented v-model:value="remoteKindFilter" :options="kindFilterOptions" size="small" />
        </Space>
      </template>
      <Empty
        v-if="!filteredRemoteModels.length"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        description="当前筛选没有远程可用模型。"
      />
      <Row v-else :gutter="[12, 12]" class="model-list-row">
        <Col v-for="item in filteredRemoteModels" :key="item.id" :xs="24">
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
                <span>{{ item.source === "comfyui" ? "ComfyUI 可用" : "本地文件" }}</span>
              </div>
              <div class="model-file" :title="item.filename">{{ item.filename }}</div>
              <div class="model-file" :title="item.path || '未配置本地路径'">{{ item.path || "未配置本地路径" }}</div>
              <Space>
                <Tag color="success">可用于生成</Tag>
                <Button
                  :type="selectedCheckpoint === item.filename ? 'primary' : 'default'"
                  :disabled="item.kind !== 'checkpoint'"
                  @click="emit('select', item)"
                >
                  <template v-if="selectedCheckpoint === item.filename" #icon><CheckOutlined /></template>
                  {{ selectedCheckpoint === item.filename ? "已选择" : "使用" }}
                </Button>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card :bordered="false" class="model-section">
      <template #title>
        <Space class="model-section-title" wrap>
          <span>本地目录模型</span>
          <Segmented v-model:value="localKindFilter" :options="kindFilterOptions" size="small" />
        </Space>
      </template>
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
                <Tooltip :title="config.mode === 'remote' ? '远程 ComfyUI 不能直接使用本机文件' : ''">
                  <Button
                    :type="selectedCheckpoint === item.filename ? 'primary' : 'default'"
                    :disabled="item.kind !== 'checkpoint' || config.mode === 'remote'"
                    @click="emit('select', item)"
                  >
                    {{ selectedCheckpoint === item.filename ? "已选择" : "使用" }}
                  </Button>
                </Tooltip>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card title="在线模型库" :bordered="false" class="model-section">
      <Alert
        v-if="!catalog.manager_available"
        type="info"
        show-icon
        message="在线模型库不可用"
        description="当前 ComfyUI 未安装或未启用 ComfyUI Manager，仅展示远程可用模型和本地目录模型。启用后即可浏览在线模型库。"
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
          <Segmented
            v-if="config.mode === 'remote'"
            v-model:value="downloadTarget"
            :options="[
              { label: '下载到远程设备', value: 'remote' },
              { label: '下载到本地路径', value: 'local' },
            ]"
          />
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
                  {{ item.installed ? "已在远程可用" : "可安装" }}
                </Tag>
                <a v-if="item.reference_url" :href="item.reference_url" target="_blank" rel="noopener">
                  <Button size="small">详情</Button>
                </a>
                <Button
                  v-if="item.installed"
                  :type="selectedCheckpoint === item.filename ? 'primary' : 'default'"
                  :disabled="item.kind !== 'checkpoint'"
                  @click="emit('select', item)"
                >
                  <template v-if="selectedCheckpoint === item.filename" #icon><CheckOutlined /></template>
                  {{ selectedCheckpoint === item.filename ? "已选择" : "使用" }}
                </Button>
                <Tooltip v-else :title="downloadTarget === 'local' ? downloadDisabledReason : ''">
                  <Button
                    type="primary"
                    :disabled="downloadTarget === 'local' && !canDownloadLocal"
                    :loading="downloadingId === item.id"
                    @click="emit('download', item.id, downloadTarget)"
                  >
                    <template #icon><CloudDownloadOutlined /></template>
                    {{ config.mode === 'remote' && downloadTarget === 'remote' ? '下载到远程' : '下载到本地' }}
                  </Button>
                </Tooltip>
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
