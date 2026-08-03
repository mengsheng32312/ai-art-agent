<script setup lang="ts">
import { computed } from "vue"
import { Alert, Button, Card, Col, Empty, Row, Space, Statistic, Tag, Tooltip } from "ant-design-vue"
import { CheckOutlined, CloudDownloadOutlined, ReloadOutlined } from "@ant-design/icons-vue"
import PageHeader from "../components/PageHeader.vue"
import type { Config, ModelCatalogResponse, ModelItem } from "../lib/api"

const props = defineProps<{
  config: Config
  catalog: ModelCatalogResponse
  selectedCheckpoint: string
  loading: boolean
  downloadingId: string
}>()

const emit = defineEmits<{
  refresh: []
  select: [model: ModelItem]
  download: [id: string]
}>()

const canDownload = computed(() => props.config.mode === "local" && Boolean(props.config.comfyui_path))
const downloadDisabledReason = computed(() => {
  if (props.config.mode !== "local") return "请切换到本地模式"
  if (!props.config.comfyui_path) return "请先填写 ComfyUI 安装目录"
  return ""
})

function kindText(kind: ModelItem["kind"]) {
  return {
    checkpoint: "Checkpoint",
    lora: "LoRA",
    controlnet: "ControlNet",
    vae: "VAE",
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
      <span class="field-help">{{ catalog.message }}</span>
      <Statistic title="本地模型" :value="catalog.local_models.length" />
      <Statistic title="在线模型" :value="catalog.online_models.length" />
    </Space>
  </Card>

  <Alert
    v-if="!catalog.connected"
    type="info"
    show-icon
    message="请先连接 ComfyUI"
    description="模型管理只展示真实 ComfyUI 模型，不再显示内置假清单。"
  />

  <template v-else>
    <Alert
      v-if="config.mode !== 'local' || !config.comfyui_path"
      class="model-section"
      type="warning"
      show-icon
      message="无法判断本地安装路径"
      description="远程模式或未填写 ComfyUI 安装目录时，只能读取 ComfyUI 当前可用模型，不能判断文件路径或下载到本地。"
    />

    <Card title="本地模型" :bordered="false" class="model-section">
      <Empty v-if="!catalog.local_models.length" description="未读取到本地模型" />
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
              <div class="model-preview">
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
        message="ComfyUI Manager 不可用"
        description="当前只展示本地模型；安装并启用 ComfyUI Manager 后可展示可下载模型。"
      />
      <Empty v-else-if="!catalog.online_models.length" description="Manager 未返回可下载模型" />
      <Row v-else :gutter="[20, 20]">
        <Col v-for="item in catalog.online_models" :key="item.id" :xs="24" :md="12" :xl="8">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span>{{ item.name }}</span>
                <Tag>{{ kindText(item.kind) }}</Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <img v-if="item.preview_url" :src="item.preview_url" :alt="item.name" class="model-preview-image" />
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
                  <Button type="primary" :disabled="!canDownload" :loading="downloadingId === item.id" @click="emit('download', item.id)">
                    <template #icon><CloudDownloadOutlined /></template>
                    下载
                  </Button>
                </Tooltip>
              </Space>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>
  </template>
</template>
