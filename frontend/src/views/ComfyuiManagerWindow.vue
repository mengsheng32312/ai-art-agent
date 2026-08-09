<script setup lang="ts">
import { LoadingOutlined } from "@ant-design/icons-vue"
import { Button, Result, Spin } from "ant-design-vue"
import { onBeforeUnmount, ref } from "vue"

const props = defineProps<{ url: string }>()
const state = ref<"loading" | "ready" | "error">("loading")
const frameKey = ref(0)
let timeoutId: ReturnType<typeof setTimeout> | undefined

function startTimeout() {
  if (timeoutId) clearTimeout(timeoutId)
  timeoutId = setTimeout(() => {
    if (state.value === "loading") state.value = "error"
  }, 30_000)
}

function markReady() {
  if (timeoutId) clearTimeout(timeoutId)
  state.value = "ready"
}

function markFailed() {
  if (timeoutId) clearTimeout(timeoutId)
  state.value = "error"
}

function retry() {
  state.value = "loading"
  frameKey.value += 1
  startTimeout()
}

startTimeout()
onBeforeUnmount(() => {
  if (timeoutId) clearTimeout(timeoutId)
})
</script>

<template>
  <main class="manager-window">
    <iframe
      :key="frameKey"
      :src="props.url"
      :class="{ 'is-ready': state === 'ready' }"
      title="ComfyUI 模型库"
      @load="markReady"
      @error="markFailed"
    />

    <section v-if="state === 'loading'" class="manager-window-state" aria-live="polite">
      <Spin size="large" :indicator="LoadingOutlined" />
      <strong>ComfyUI 模型库正在加载</strong>
      <span>首次打开可能需要一些时间</span>
    </section>

    <section v-else-if="state === 'error'" class="manager-window-state" aria-live="assertive">
      <Result
        status="warning"
        title="ComfyUI 模型库加载超时"
        sub-title="请确认 ComfyUI 页面可以正常访问后重试"
      >
        <template #extra>
          <Button type="primary" @click="retry">重新加载</Button>
        </template>
      </Result>
    </section>
  </main>
</template>

<style scoped>
.manager-window {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: var(--surface);
}

.manager-window iframe {
  width: 100%;
  height: 100%;
  opacity: 0;
  border: 0;
}

.manager-window iframe.is-ready {
  opacity: 1;
}

.manager-window-state {
  position: absolute;
  inset: 0;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 12px;
  padding: 24px;
  color: var(--text);
  text-align: center;
  background: var(--surface);
}

.manager-window-state strong {
  font-size: 15px;
}

.manager-window-state span {
  color: var(--text-secondary);
  font-size: 12px;
}
</style>
