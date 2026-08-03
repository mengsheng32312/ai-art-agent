<script setup lang="ts">
import { Alert, Button, Card, Collapse, Form, Input, InputNumber, Select, Space, Tooltip } from "ant-design-vue"
import { ThunderboltOutlined } from "@ant-design/icons-vue"
import type { GenerationRequest } from "../lib/api"

defineProps<{
  form: GenerationRequest
  checkpoints: string[]
  canGenerate: boolean
  blockedReason: string
  busy: boolean
  notice: string
}>()

const emit = defineEmits<{ generate: []; goModels: [] }>()

function submit() {
  emit("generate")
}
</script>

<template>
  <Card title="生成参数" :bordered="false">
    <Form layout="vertical">
      <Form.Item
        label="画面描述"
        :validate-status="blockedReason === '请输入画面描述' ? 'error' : undefined"
        :help="blockedReason === '请输入画面描述' ? blockedReason : undefined"
      >
        <Input.TextArea v-model:value="form.prompt" :rows="5" placeholder="例如：薄雾中的东方古城，电影级光影" />
      </Form.Item>

      <Form.Item label="排除内容">
        <Input.TextArea v-model:value="form.negative_prompt" :rows="2" placeholder="模糊、低质量、文字" />
      </Form.Item>

      <div class="form-section-title">基础参数</div>
      <Space class="form-row" align="start">
        <Form.Item
          label="模型"
          class="form-main"
          :validate-status="blockedReason.includes('模型') || blockedReason.includes('ComfyUI') ? 'error' : undefined"
          :help="blockedReason.includes('模型') ? blockedReason : undefined"
        >
          <Select v-model:value="form.checkpoint" placeholder="请选择 checkpoint" :not-found-content="'暂无可用模型'">
            <Select.Option v-for="item in checkpoints" :key="item" :value="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="生成数量">
          <InputNumber v-model:value="form.batch_size" :min="1" :max="8" />
        </Form.Item>
      </Space>

      <Space class="form-row" align="start">
        <Form.Item label="宽度" extra="64-4096，建议按 64 调整">
          <InputNumber v-model:value="form.width" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item label="高度" extra="64-4096，建议按 64 调整">
          <InputNumber v-model:value="form.height" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item label="随机种子">
          <InputNumber v-model:value="form.seed" />
        </Form.Item>
      </Space>

      <Collapse ghost>
        <Collapse.Panel key="advanced" header="高级参数">
          <Space class="form-row" align="start">
            <Form.Item label="步数" extra="1-150，越高越慢">
              <InputNumber v-model:value="form.steps" :min="1" :max="150" />
            </Form.Item>
            <Form.Item label="CFG" extra="0-30，控制提示词强度">
              <InputNumber v-model:value="form.cfg" :min="0" :max="30" :step="0.5" />
            </Form.Item>
            <Form.Item label="采样器">
              <Select v-model:value="form.sampler">
                <Select.Option value="euler">euler</Select.Option>
                <Select.Option value="dpmpp_2m">dpmpp_2m</Select.Option>
              </Select>
            </Form.Item>
          </Space>
        </Collapse.Panel>
      </Collapse>

      <Alert v-if="blockedReason && !busy" class="form-notice" type="warning" show-icon :message="blockedReason" />

      <Button
        v-if="blockedReason.includes('模型')"
        block
        class="form-secondary-action"
        @click="emit('goModels')"
      >
        去模型管理
      </Button>

      <Tooltip :title="!canGenerate ? blockedReason : ''">
        <Button type="primary" block size="large" :loading="busy" :disabled="!canGenerate" @click="submit">
          <template #icon><ThunderboltOutlined /></template>
          {{ busy ? "正在提交" : "开始生成" }}
        </Button>
      </Tooltip>

      <Alert v-if="notice" class="form-notice" type="info" show-icon :message="notice" />
    </Form>
  </Card>
</template>
