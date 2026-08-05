<script setup lang="ts">
import { ref, watch } from "vue"
import { Alert, Card, Empty, Progress, Spin } from "ant-design-vue"
import { proxiedImageUrl, type GenerationTask } from "../lib/api"

const props = defineProps<{ task: GenerationTask | null; blockedReason: string }>()

const imageLoaded = ref(false)
const imageError = ref(false)
const retryKey = ref(0)

function isVideoUrl(url: string | undefined): boolean {
  if (!url) return false
  const path = url.split("?")[0].toLowerCase()
  return /\.(mp4|webm|mov|avi|mkv)$/.test(path)
}

watch(
  () => props.task?.outputs[0],
  () => {
    imageLoaded.value = false
    imageError.value = false
  },
)

function retryImage() {
  imageLoaded.value = false
  imageError.value = false
  retryKey.value += 1
}
</script>

<template>
  <Card title="结果预览" :bordered="false" class="preview-card">
    <div v-if="task?.outputs[0]" class="preview-image-wrap">
      <video
        v-if="isVideoUrl(task.outputs[0])"
        :key="retryKey"
        v-show="imageLoaded"
        :src="proxiedImageUrl(task.outputs[0])"
        controls
        class="preview-image"
        @loadeddata="imageLoaded = true; imageError = false"
        @error="imageError = true"
      />
      <img
        v-else
        :key="retryKey"
        v-show="imageLoaded"
        :src="proxiedImageUrl(task.outputs[0])"
        alt="生成结果"
        class="preview-image"
        @load="imageLoaded = true; imageError = false"
        @error="imageError = true"
      />
      <div v-if="!imageLoaded && !imageError" class="preview-empty">
        <Spin size="large" />
        <div class="preview-hint">图片加载中…</div>
      </div>
      <div v-else-if="imageError" class="preview-empty">
        <Alert
          type="error"
          show-icon
          message="图片加载失败"
          description="远程图片暂时无法访问，可能是隧道网络不稳定，请重试。"
        />
        <Button class="preview-retry" @click="retryImage">重新加载</Button>
      </div>
    </div>
    <div v-else-if="task?.status === 'failed'" class="preview-empty">
      <Alert type="error" show-icon message="生成失败" :description="task.error || 'ComfyUI 返回失败状态'" />
      <Progress :percent="task.progress" status="exception" />
    </div>
    <div v-else class="preview-empty">
      <Spin v-if="task" size="large" />
      <Empty
        v-else
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        :description="blockedReason || '生成结果会显示在这里'"
      />
      <Progress v-if="task" :percent="task.progress" active />
    </div>
  </Card>
</template>
