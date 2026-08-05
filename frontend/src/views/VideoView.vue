<script setup lang="ts">
import { Col, Row } from "ant-design-vue"
import type { GenerationRequest, GenerationTask } from "../lib/api"
import GenerationForm from "../components/GenerationForm.vue"
import GenerationPreview from "../components/GenerationPreview.vue"

defineProps<{
  form: GenerationRequest
  checkpoints: string[]
  vaeModels: string[]
  currentTask: GenerationTask | null
  canGenerate: boolean
  blockedReason: string
  submissionAttempted: boolean
  busy: boolean
  notice: string
  noticeType: "info" | "success" | "error"
  motionModels: string[]
}>()

const emit = defineEmits<{ generate: []; goModels: [] }>()
</script>

<template>
  <div class="page-workspace generation-page">
    <Row :gutter="[16, 16]">
      <Col :xs="24" :xl="11">
        <GenerationForm
          :form="form"
          :checkpoints="checkpoints"
          :vae-models="vaeModels"
          :can-generate="canGenerate"
          :blocked-reason="blockedReason"
          :submission-attempted="submissionAttempted"
          :busy="busy"
          :notice="notice"
          :notice-type="noticeType"
          :mode="'video'"
          :motion-models="motionModels"
          @go-models="emit('goModels')"
          @generate="emit('generate')"
        />
      </Col>
      <Col :xs="24" :xl="13">
        <GenerationPreview :task="currentTask" :blocked-reason="submissionAttempted ? blockedReason : ''" />
      </Col>
    </Row>
  </div>
</template>
