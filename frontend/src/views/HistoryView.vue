<script setup lang="ts">
import { computed, h, ref } from "vue"
import { Button, Card, Empty, List, Modal, Popconfirm, Segmented, Space, Tag, Tooltip } from "ant-design-vue"
import {
  DeleteOutlined,
  DownloadOutlined,
  FolderOpenOutlined,
  PictureOutlined,
  RedoOutlined,
} from "@ant-design/icons-vue"
import {
  proxiedImageUrl,
  resolveSaveLocation,
  type Config,
  type GenerationTask,
} from "../lib/api"
import PageHeader from "../components/PageHeader.vue"

const props = defineProps<{ history: GenerationTask[]; config: Config }>()

const emit = defineEmits<{
  redraw: [task: GenerationTask]
  remove: [id: string]
  openLocation: [task: GenerationTask]
}>()

const statusFilter = ref<"all" | GenerationTask["status"]>("completed")
const mediaFilter = ref<"all" | "image" | "video">("all")
const detailTask = ref<GenerationTask | null>(null)
const detailVisible = ref(false)

const statusOptions = [
  { label: "全部", value: "all" },
  { label: "排队", value: "queued" },
  { label: "运行中", value: "running" },
  { label: "完成", value: "completed" },
  { label: "失败", value: "failed" },
]

const mediaOptions = [
  { label: "全部", value: "all" },
  { label: "图片", value: "image" },
  { label: "视频", value: "video" },
]

function mediaKind(task: GenerationTask): "image" | "video" | null {
  const url = task.outputs[0]
  if (!url) return null
  const path = url.split("?")[0].toLowerCase()
  if (/\.(webp)$/.test(path)) return "video"
  if (/\.(png|jpe?g|bmp|gif)$/.test(path)) return "image"
  if (/\.(mp4|webm|mov|avi|mkv)$/.test(path)) return "video"
  return null
}

function displayAsVideo(task: GenerationTask): boolean {
  const url = task.outputs[0]
  if (!url) return false
  const path = url.split("?")[0].toLowerCase()
  return /\.(mp4|webm|mov|avi|mkv)$/.test(path)
}

const filteredHistory = computed(() =>
  props.history.filter(item => {
    if (statusFilter.value !== "all" && item.status !== statusFilter.value) return false
    if (mediaFilter.value === "all") return true
    return mediaKind(item) === mediaFilter.value
  }),
)

function statusColor(status: GenerationTask["status"]) {
  return status === "completed"
    ? "success"
    : status === "failed"
      ? "error"
      : "processing"
}

function statusLabel(status: GenerationTask["status"]) {
  return status === "completed" ? "完成" : status === "failed" ? "失败" : status
}

function showDetail(task: GenerationTask) {
  detailTask.value = task
  detailVisible.value = true
}

function buildWorkflowExport(task: GenerationTask) {
  const r = task.request
  return {
    version: "0.1.0",
    generated_by: "AI Art Agent",
    prompt_id: task.prompt_id,
    created_at: new Date().toISOString(),
    workflow: {
      last_node_id: 7,
      nodes: [
        { id: 1, type: "CheckpointLoaderSimple", inputs: { ckpt_name: r.checkpoint } },
        { id: 2, type: "CLIPTextEncode", inputs: { text: r.prompt, clip: ["1", 1] } },
        { id: 3, type: "CLIPTextEncode", inputs: { text: r.negative_prompt, clip: ["1", 1] } },
        {
          id: 4,
          type: "EmptyLatentImage",
          inputs: { width: r.width, height: r.height, batch_size: r.batch_size },
        },
        {
          id: 5,
          type: "KSampler",
          inputs: {
            seed: r.seed,
            steps: r.steps,
            cfg: r.cfg,
            sampler_name: r.sampler,
            scheduler: r.scheduler,
            denoise: 1,
            model: ["1", 0],
            positive: ["2", 0],
            negative: ["3", 0],
            latent_image: ["4", 0],
          },
        },
        { id: 6, type: "VAEDecode", inputs: { samples: ["5", 0], vae: ["1", 2] } },
        { id: 7, type: "SaveImage", inputs: { filename_prefix: "AIArtAgent", images: ["6", 0] } },
      ],
    },
  }
}

function downloadWorkflow(task: GenerationTask) {
  const blob = new Blob([JSON.stringify(buildWorkflowExport(task), null, 2)], {
    type: "application/json",
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `workflow-${task.prompt_id ?? task.id}.json`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <PageHeader title="历史记录" description="查看最近提交的生成任务，可重新绘制、导出节点或删除。" />

  <Card v-if="history.length" :bordered="false" class="history-toolbar">
    <Space wrap class="history-toolbar-content">
      <Segmented v-model:value="statusFilter" :options="statusOptions" />
      <Segmented v-model:value="mediaFilter" :options="mediaOptions" />
    </Space>
  </Card>

  <Empty
    v-if="!history.length"
    :image="Empty.PRESENTED_IMAGE_SIMPLE"
    description="还没有生成记录，提交生成任务后会显示在这里。"
  />
  <Empty
    v-else-if="!filteredHistory.length"
    :image="Empty.PRESENTED_IMAGE_SIMPLE"
    description="当前筛选下没有记录"
  />

  <List v-else :grid="{ gutter: 16, xs: 1, sm: 2, lg: 3, xl: 4 }" :data-source="filteredHistory">
    <template #renderItem="{ item }">
      <List.Item>
        <Card hoverable class="history-card">
          <template #cover>
            <div class="history-cover" @click="showDetail(item)">
              <img
                v-if="item.outputs[0] && !displayAsVideo(item)"
                :src="proxiedImageUrl(item.outputs[0])"
                alt="历史结果"
              />
              <video
                v-else-if="item.outputs[0] && displayAsVideo(item)"
                :src="proxiedImageUrl(item.outputs[0])"
                controls
                class="history-cover-media"
              />
              <PictureOutlined v-else-if="item.status === 'completed'" />
              <span v-else class="history-cover-text">{{ statusLabel(item.status) }}</span>
            </div>
          </template>
          <Card.Meta :title="item.request.prompt || '未命名任务'">
            <template #description>
              <div class="history-meta">
                <span>{{ item.request.checkpoint || "未选择模型" }}</span>
                <span>{{ item.request.width }}x{{ item.request.height }}</span>
                <Tag :color="statusColor(item.status)">{{ statusLabel(item.status) }}</Tag>
              </div>
            </template>
          </Card.Meta>
          <div v-if="item.status === 'completed'" class="history-actions">
            <Tooltip title="查看保存位置">
              <Button size="small" :icon="h(FolderOpenOutlined)" @click="showDetail(item)" />
            </Tooltip>
            <Tooltip title="导出节点（工作流 JSON）">
              <Button size="small" :icon="h(DownloadOutlined)" @click="downloadWorkflow(item)" />
            </Tooltip>
            <Tooltip title="再次绘制">
              <Button size="small" :icon="h(RedoOutlined)" @click="emit('redraw', item)" />
            </Tooltip>
            <Popconfirm title="确定删除这条记录？" @confirm="emit('remove', item.id)">
              <Tooltip title="删除">
                <Button size="small" danger :icon="h(DeleteOutlined)" />
              </Tooltip>
            </Popconfirm>
          </div>
          <div v-else class="history-actions">
            <Popconfirm title="确定删除这条记录？" @confirm="emit('remove', item.id)">
              <Button size="small" danger :icon="h(DeleteOutlined)">删除</Button>
            </Popconfirm>
          </div>
        </Card>
      </List.Item>
    </template>
  </List>

  <Modal
    v-model:open="detailVisible"
    title="结果详情"
    :footer="null"
    width="560px"
    destroy-on-close
  >
    <template v-if="detailTask">
      <div class="history-detail-preview">
        <img
          v-if="detailTask.outputs[0] && !displayAsVideo(detailTask)"
          :src="proxiedImageUrl(detailTask.outputs[0])"
          alt="生成结果"
        />
        <video
          v-else-if="detailTask.outputs[0] && displayAsVideo(detailTask)"
          :src="proxiedImageUrl(detailTask.outputs[0])"
          controls
          class="history-cover-media"
        />
      </div>
      <div class="history-detail-row">
        <span class="history-detail-label">{{ resolveSaveLocation(detailTask, config)?.label ?? "位置" }}</span>
        <code class="history-detail-path">{{ resolveSaveLocation(detailTask, config)?.text }}</code>
      </div>
      <Button
        v-if="detailTask.status === 'completed'"
        type="primary"
        block
        @click="emit('openLocation', detailTask)"
      >
        打开位置
      </Button>
    </template>
  </Modal>
</template>
