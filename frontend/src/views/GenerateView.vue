<script setup lang="ts">
import { Col, Row } from "ant-design-vue"
import type { GenerationRequest, GenerationTask } from "../lib/api"
import GenerationForm from "../components/GenerationForm.vue"
import GenerationPreview from "../components/GenerationPreview.vue"
import PageHeader from "../components/PageHeader.vue"

defineProps<{
  form: GenerationRequest
  checkpoints: string[]
  currentTask: GenerationTask | null
  canGenerate: boolean
  blockedReason: string
  busy: boolean
  notice: string
}>()

const emit = defineEmits<{ generate: []; goModels: [] }>()
</script>

<template>
  <PageHeader title="生成图片" description="填写提示词和常用参数，提交到预设工作流。" />
  <Row :gutter="[20, 20]">
    <Col :xs="24" :xl="11">
      <GenerationForm
        :form="form"
        :checkpoints="checkpoints"
        :can-generate="canGenerate"
        :blocked-reason="blockedReason"
        :busy="busy"
        :notice="notice"
        @go-models="emit('goModels')"
        @generate="emit('generate')"
      />
    </Col>
    <Col :xs="24" :xl="13">
      <GenerationPreview :task="currentTask" :blocked-reason="blockedReason" />
    </Col>
  </Row>
</template>
