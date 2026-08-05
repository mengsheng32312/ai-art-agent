<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Alert, Button, Card, Col, Empty, Pagination, Row, Segmented, Space, Statistic, Tag, Tooltip } from "ant-design-vue"
import { CheckOutlined, CloudDownloadOutlined, ReloadOutlined } from "@ant-design/icons-vue"
import PageHeader from "../components/PageHeader.vue"
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

const canDownload = computed(() => Boolean(props.config.comfyui_path))
const downloadDisabledReason = computed(() => {
  if (!props.config.comfyui_path) return "请先在连接设置填写模型下载目录（本地 ComfyUI 目录）"
  return ""
})

const kindFilter = ref<"all" | ModelItem["kind"]>("all")
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
const filteredOnlineModels = computed(() =>
  kindFilter.value === "all"
    ? props.catalog.online_models
    : props.catalog.online_models.filter(item => item.kind === kindFilter.value),
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

function kindText(kind: ModelItem["kind"]) {
  return {
    checkpoint: "Checkpoint",
    lora: "LoRA",
    controlnet: "ControlNet",
    vae: "VAE",
    other: "其他",
  }[kind]
}
</script>

<template>
  <PageHeader title="模型管理" description="读取 ComfyUI 实际模型，连接后可选择和下载。" />

  <Card :bordered="false" class="model-toolbar">
    <Space class="model-toolbar-content">
      <Button :loading="loading" @click="emit('refresh')">
        <template #icon><ReloadOutlined /></template>
        刷新模型
      </Button>
      <span v-if="connected" class="field-help">{{ catalog.message }}</span>
      <Statistic title="本地模型" :value="catalog.local_models.length" />
      <Statistic title="在线模型" :value="catalog.online_models.length" />
    </Space>
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
      description="当前为远程连接模式，仅能读取远程 ComfyUI 的可用模型。如需将模型下载到本地，请在「连接设置」中填写模型下载目录。"
    />

    <Card title="本地模型" :bordered="false" class="model-section">
      <Empty
        v-if="!catalog.local_models.length"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        description="暂无可用模型，请连接 ComfyUI 后刷新。"
      />
      <Row v-else :gutter="[20, 20]">
        <Col v-for="item in catalog.local_models" :key="item.id" :xs="24" :md="12" :xl="8">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span>{{ item.name }}</span>
                <Tag>{{ kindText(item.kind) }}</Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="proxiedImageUrl(item.preview_url)" :alt="item.name" class="model-preview-image" />
              <div v-else class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ item.source === "comfyui" ? "ComfyUI 可用" : "本地文件" }}</span>
              </div>
              <div class="model-file">{{ item.filename }}</div>
              <div class="model-file">{{ item.path || "未配置本地路径" }}</div>
              <Space>
                <Tag color="success">已存在</Tag>
                <Button
                  :type="selectedCheckpoint === item.filename ? 'primary' : 'default'"
                  :disabled="item.kind !== 'checkpoint'"
                  @click="emit('select', item)"
                >
                  <template v-if="selectedCheckpoint === item.filename" #icon><CheckOutlined /></template>
                  {{ selectedCheckpoint === item.filename ? "当前使用" : "使用" }}
                </Button>
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
        description="当前 ComfyUI 未安装或未启用 ComfyUI Manager，仅展示本地模型。启用后即可浏览在线模型库。"
      />
      <template v-else>
        <Alert
          class="model-section"
          type="info"
          show-icon
          message="模型下载说明"
          description="下载到远程设备：模型将安装至远程 ComfyUI，刷新后可在生成页选择使用。下载到本地路径：文件仅保存至本地目录，远程生成不会调用；本地 ComfyUI 模式下下载的模型可直接用于生成。"
        />
        <Space class="model-toolbar-content">
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
        <Row v-else :gutter="[20, 20]" class="model-section">
        <Col v-for="item in pagedOnlineModels" :key="item.id" :xs="24" :md="12" :xl="8">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span>{{ item.name }}</span>
                <Tag>{{ kindText(item.kind) }}</Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="proxiedImageUrl(item.preview_url)" :alt="item.name" class="model-preview-image" />
              <div v-else class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ item.size_label || "Manager 模型库" }}</span>
              </div>
              <p class="model-desc">{{ item.description }}</p>
              <div class="model-file">{{ item.filename }}</div>
              <Space>
                <Tag :color="item.installed ? 'success' : 'default'">
                  {{ item.installed ? "已存在" : "未下载" }}
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
                  {{ selectedCheckpoint === item.filename ? "当前使用" : "使用" }}
                </Button>
                <Tooltip v-else :title="downloadDisabledReason">
                  <Button
                    type="primary"
                    :disabled="!canDownload"
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
</template>
