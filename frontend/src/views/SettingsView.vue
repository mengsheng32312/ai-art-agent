<script setup lang="ts">
import { computed } from "vue"
import { Alert, Button, Card, Form, Input, Segmented } from "ant-design-vue"
import type { Config } from "../lib/api"

const props = defineProps<{
  config: Config
  connected: boolean
  connectionMessage: string
  busy: boolean
  testingConnection: boolean
  notice: string
  noticeType: "info" | "success" | "error"
  settingsError: string
}>()

const emit = defineEmits<{
  clear: []
  chooseDirectory: []
  refresh: []
}>()

const modeOptions = [
  { label: "本地 ComfyUI", value: "local" },
  { label: "远程 API", value: "remote" },
]

// Status details belong in the status area; action notices stay separate.
const shouldShowConnectionDetail = computed(() => !props.testingConnection && (props.connected || props.connectionMessage !== "尚未连接"))
</script>

<template>
  <div class="page-workspace settings-page">
    <Card class="settings-card" :bordered="false">
      <Form layout="vertical">
        <Form.Item label="连接模式">
          <Segmented v-model:value="config.mode" :options="modeOptions" block @change="emit('clear')" />
        </Form.Item>

        <Form.Item
          v-if="config.mode === 'local'"
          label="ComfyUI 安装目录"
          :validate-status="settingsError ? 'error' : undefined"
          :help="settingsError || undefined"
        >
          <div class="inline-control-row">
            <Input
              :value="config.comfyui_path ?? ''"
              placeholder="D:\ComfyUI"
              @update:value="value => { config.comfyui_path = value; emit('clear') }"
            />
            <Button @click="emit('chooseDirectory')">选择目录</Button>
          </div>
          <div class="field-help">请选择包含 main.py 的 ComfyUI 目录，或 Windows Portable 根目录。</div>
        </Form.Item>

        <Form.Item
          v-if="config.mode === 'remote'"
          label="API 地址"
          :validate-status="settingsError ? 'error' : undefined"
          :help="settingsError || undefined"
        >
          <Input v-model:value="config.api_url" placeholder="http://127.0.0.1:8188" @input="emit('clear')" />
        </Form.Item>

        <Form.Item
          v-if="config.mode === 'remote'"
          label="本地模型目录"
          :validate-status="settingsError ? 'error' : undefined"
          :help="settingsError || undefined"
        >
          <div class="inline-control-row">
            <Input
              :value="config.comfyui_path ?? ''"
              placeholder="D:\ComfyUI"
              @update:value="value => { config.comfyui_path = value; emit('clear') }"
            />
            <Button @click="emit('chooseDirectory')">选择目录</Button>
          </div>
          <div class="field-help">用于扫描本机真实模型文件；远程 ComfyUI 不能直接使用这些本机文件。</div>
        </Form.Item>

        <Alert
          show-icon
          :type="connected ? 'success' : 'info'"
          :message="testingConnection ? connectionMessage : connected ? '连接正常' : '尚未连接'"
          :description="shouldShowConnectionDetail ? connectionMessage : undefined"
        />

        <div class="settings-actions">
          <Button :loading="testingConnection" :disabled="busy" @click="emit('refresh')">测试连接</Button>
        </div>

        <Alert v-if="notice && !testingConnection" class="form-notice" show-icon :type="noticeType" :message="notice" />
      </Form>
    </Card>
  </div>
</template>
