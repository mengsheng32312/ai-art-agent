<script setup lang="ts">
import { computed, ref } from "vue"
import { Alert, Card, Empty, List, Segmented, Tag } from "ant-design-vue"
import { PictureOutlined } from "@ant-design/icons-vue"
import type { GenerationTask } from "../lib/api"
import PageHeader from "../components/PageHeader.vue"

const props = defineProps<{ history: GenerationTask[] }>()
const statusFilter = ref<"all" | GenerationTask["status"]>("all")

const filterOptions = [
  { label: "全部", value: "all" },
  { label: "排队", value: "queued" },
  { label: "运行中", value: "running" },
  { label: "完成", value: "completed" },
  { label: "失败", value: "failed" },
]

const filteredHistory = computed(() =>
  statusFilter.value === "all"
    ? props.history
    : props.history.filter(item => item.status === statusFilter.value),
)
</script>

<template>
  <PageHeader title="历史记录" description="查看最近提交的生成任务。" />

  <Card v-if="history.length" :bordered="false" class="history-toolbar">
    <Segmented v-model:value="statusFilter" :options="filterOptions" />
  </Card>

  <Empty v-if="!history.length" description="还没有生成记录，提交生成任务后会显示在这里。" />
  <Empty v-else-if="!filteredHistory.length" description="当前筛选下没有记录" />

  <List v-else :grid="{ gutter: 16, xs: 1, sm: 2, lg: 3, xl: 4 }" :data-source="filteredHistory">
    <template #renderItem="{ item }">
      <List.Item>
        <Card hoverable>
          <template #cover>
            <div class="history-cover">
              <img v-if="item.outputs[0]" :src="item.outputs[0]" alt="历史结果" />
              <PictureOutlined v-else />
            </div>
          </template>
          <Card.Meta :title="item.request.prompt || '未命名任务'">
            <template #description>
              <div class="history-meta">
                <span>{{ item.request.checkpoint || "未选择模型" }}</span>
                <span>{{ item.request.width }}x{{ item.request.height }}</span>
                <Tag :color="item.status === 'completed' ? 'success' : item.status === 'failed' ? 'error' : 'processing'">{{ item.status }}</Tag>
                <Alert v-if="item.status === 'failed' && item.error" type="error" show-icon :message="item.error" />
              </div>
            </template>
          </Card.Meta>
        </Card>
      </List.Item>
    </template>
  </List>
</template>
