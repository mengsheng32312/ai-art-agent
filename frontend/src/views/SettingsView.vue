<script setup lang="ts">
import { computed } from "vue"
import { Alert, Button, Card, Form, Input, Segmented, Space } from "ant-design-vue"
import type { Config } from "../lib/api"
import PageHeader from "../components/PageHeader.vue"

const props = defineProps<{
  config: Config
  connected: boolean
  connectionMessage: string
  busy: boolean
  testingConnection: boolean
  notice: string
  settingsError: string
}>()

const emit = defineEmits<{
  clear: []
  refresh: []
  save: []
}>()

const modeOptions = [
  { label: "本地 ComfyUI", value: "local" },
  { label: "远程 API", value: "remote" },
]

// Status details belong in the status area; action notices stay separate.
const shouldShowConnectionDetail = computed(() => props.testingConnection || props.connected || props.connectionMessage !== "尚未连接")
</script>

<template>
  <PageHeader title="连接设置" description="配置本机或其他电脑上的 ComfyUI。" />

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
        <Space.Compact block>
          <Input
            :value="config.comfyui_path ?? ''"
            placeholder="D:\ComfyUI"
            @update:value="value => { config.comfyui_path = value; emit('clear') }"
          />
          <Button disabled title="当前 Web 版不支持浏览本机目录">选择目录</Button>
        </Space.Compact>
        <div class="field-help">当前先手动填写目录；例如 D:\ComfyUI。</div>
      </Form.Item>

      <Form.Item
        v-if="config.mode === 'remote'"
        label="API 地址"
        :validate-status="settingsError ? 'error' : undefined"
        :help="settingsError || undefined"
      >
        <Input v-model:value="config.api_url" placeholder="http://127.0.0.1:8188" @input="emit('clear')" />
      </Form.Item>

      <Alert
        show-icon
        :type="connected ? 'success' : 'info'"
        :message="testingConnection ? '正在测试连接' : connected ? '连接正常' : '尚未连接'"
        :description="shouldShowConnectionDetail ? connectionMessage : undefined"
      />

      <div class="settings-actions">
        <Button :loading="testingConnection" :disabled="busy" @click="emit('refresh')">测试连接</Button>
        <Button type="primary" :loading="busy" :disabled="testingConnection" @click="emit('save')">保存设置</Button>
      </div>

      <Alert v-if="notice === '设置已保存'" class="form-notice" show-icon type="success" :message="notice" />
    </Form>
  </Card>
</template>
