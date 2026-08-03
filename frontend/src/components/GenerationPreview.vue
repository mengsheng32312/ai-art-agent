<script setup lang="ts">
import { Alert, Card, Empty, Progress, Spin } from "ant-design-vue"
import type { GenerationTask } from "../lib/api"

defineProps<{ task: GenerationTask | null; blockedReason: string }>()
</script>

<template>
  <Card title="结果预览" :bordered="false" class="preview-card">
    <img v-if="task?.outputs[0]" :src="task.outputs[0]" alt="生成结果" class="preview-image" />
    <div v-else-if="task?.status === 'failed'" class="preview-empty">
      <Alert type="error" show-icon message="生成失败" :description="task.error || 'ComfyUI 返回失败状态'" />
      <Progress :percent="task.progress" status="exception" />
    </div>
    <div v-else class="preview-empty">
      <Spin v-if="task" size="large" />
      <Empty v-else :description="blockedReason || '生成结果会显示在这里'" />
      <Progress v-if="task" :percent="task.progress" active />
    </div>
  </Card>
</template>
