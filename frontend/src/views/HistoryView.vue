<script setup lang="ts">
import { computed, h, ref } from "vue"
import { Button, Card, Empty, List, Modal, Popconfirm, Select, Tag, Tooltip } from "ant-design-vue"
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

const props = defineProps<{ history: GenerationTask[]; config: Config }>()

const emit = defineEmits<{
  redraw: [task: GenerationTask]
  remove: [id: string]
  openLocation: [task: GenerationTask]
}>()

const detailTask = ref<GenerationTask | null>(null)
const detailVisible = ref(false)
const typeFilter = ref<"all" | "text-image" | "image-image" | "video">("all")
const brokenImages = ref<Record<string, boolean>>({})

const typeOptions = [
  { label: "全部", value: "all" },
  { label: "文生图", value: "text-image" },
  { label: "图生图", value: "image-image" },
  { label: "视频", value: "video" },
]

function taskType(task: GenerationTask): "text-image" | "image-image" | "video" {
  if (task.request.media_type === "video") return "video"
  return task.request.denoise < 1 ? "image-image" : "text-image"
}

const filteredHistory = computed(() =>
  typeFilter.value === "all"
    ? props.history
    : props.history.filter(item => taskType(item) === typeFilter.value),
)

function displayAsVideo(task: GenerationTask): boolean {
  const url = task.outputs[0]
  if (!url) return false
  const path = url.split("?")[0].toLowerCase()
  return /\.(mp4|webm|mov|avi|mkv)$/.test(path)
}

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

function typeLabel(task: GenerationTask) {
  return {
    "text-image": "文生图",
    "image-image": "图生图",
    video: "视频",
  }[taskType(task)]
}

function showDetail(task: GenerationTask) {
  detailTask.value = task
  detailVisible.value = true
}

function markImageBroken(id: string) {
  brokenImages.value[id] = true
}

function imageBroken(id: string) {
  return Boolean(brokenImages.value[id])
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
  <div class="page-workspace page-scroll history-page">
  <Card :bordered="false" class="history-toolbar">
    <div class="history-toolbar-content">
      <Select
        v-model:value="typeFilter"
        class="history-filter"
        :options="typeOptions"
      />
    </div>
  </Card>
  <div v-if="!history.length" class="history-empty">
    <Empty
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
      description="还没有生成记录，提交生成任务后会显示在这里。"
    />
  </div>
  <div v-else-if="!filteredHistory.length" class="history-empty">
    <Empty
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
      description="当前筛选下没有记录"
    />
  </div>

  <List v-else class="history-list" :data-source="filteredHistory">
    <template #renderItem="{ item }">
      <List.Item class="history-list-item">
        <div class="history-thumb" @click="showDetail(item)">
          <img
            v-if="item.outputs[0] && !displayAsVideo(item) && !imageBroken(item.id)"
            :src="proxiedImageUrl(item.outputs[0])"
            alt="历史结果"
            @error="markImageBroken(item.id)"
          />
          <video
            v-else-if="item.outputs[0] && displayAsVideo(item)"
            :src="proxiedImageUrl(item.outputs[0])"
            muted
            class="history-cover-media"
          />
          <div v-else-if="item.status === 'completed'" class="history-thumb-fallback">
            <PictureOutlined />
            <span>图片不可用</span>
          </div>
          <span v-else class="history-cover-text">{{ statusLabel(item.status) }}</span>
        </div>

        <div class="history-info">
          <div class="history-meta">
            <Tag>{{ typeLabel(item) }}</Tag>
            <span>{{ item.request.width }} × {{ item.request.height }}</span>
            <span>{{ item.request.checkpoint || "未选择模型" }}</span>
            <Tag :color="statusColor(item.status)">{{ statusLabel(item.status) }}</Tag>
          </div>
        </div>

        <div class="history-actions">
          <template v-if="item.status === 'completed'">
            <Tooltip title="查看保存位置">
              <Button class="history-action-btn" size="small" :icon="h(FolderOpenOutlined)" @click="showDetail(item)" />
            </Tooltip>
            <Tooltip title="导出节点（工作流 JSON）">
              <Button class="history-action-btn" size="small" :icon="h(DownloadOutlined)" @click="downloadWorkflow(item)" />
            </Tooltip>
            <Tooltip title="再次绘制">
              <Button class="history-action-btn" size="small" :icon="h(RedoOutlined)" @click="emit('redraw', item)" />
            </Tooltip>
            <Popconfirm title="确定删除这条记录？" @confirm="emit('remove', item.id)">
              <Tooltip title="删除">
                <Button class="history-action-btn" size="small" danger :icon="h(DeleteOutlined)" />
              </Tooltip>
            </Popconfirm>
          </template>
          <template v-else>
            <Popconfirm title="确定删除这条记录？" @confirm="emit('remove', item.id)">
              <Button size="small" danger :icon="h(DeleteOutlined)">删除</Button>
            </Popconfirm>
          </template>
        </div>
      </List.Item>
    </template>
  </List>

  <Modal
    v-model:open="detailVisible"
    title="结果详情"
    :footer="null"
    width="min(920px, 92vw)"
    destroy-on-close
  >
    <template v-if="detailTask">
      <div class="history-detail-preview">
        <img
          v-if="detailTask.outputs[0] && !displayAsVideo(detailTask) && !imageBroken(detailTask.id)"
          :src="proxiedImageUrl(detailTask.outputs[0])"
          alt="生成结果"
          @error="markImageBroken(detailTask.id)"
        />
        <video
          v-else-if="detailTask.outputs[0] && displayAsVideo(detailTask)"
          :src="proxiedImageUrl(detailTask.outputs[0])"
          controls
          class="history-cover-media"
        />
        <div v-else class="history-detail-fallback">
          <PictureOutlined />
          <span>图片不可用</span>
        </div>
      </div>
      <div class="history-detail-row">
        <span class="history-detail-label">结果信息</span>
        <div class="history-detail-meta">
          <Tag>{{ typeLabel(detailTask) }}</Tag>
          <Tag :color="statusColor(detailTask.status)">{{ statusLabel(detailTask.status) }}</Tag>
          <span>{{ detailTask.request.width }} × {{ detailTask.request.height }}</span>
        </div>
        <code class="history-detail-path">{{ resolveSaveLocation(detailTask, config)?.text }}</code>
      </div>
      <Button
        v-if="detailTask.status === 'completed' && resolveSaveLocation(detailTask, config)?.kind === 'path'"
        type="primary"
        block
        @click="emit('openLocation', detailTask)"
      >
        打开位置
      </Button>
    </template>
  </Modal>
  </div>
</template>
