<script setup lang="ts">
import { Tooltip } from "ant-design-vue"
import { QuestionCircleOutlined } from "@ant-design/icons-vue"

defineProps<{ label: string; help: string }>()
</script>

<template>
  <span class="field-label">
    {{ label }}
    <Tooltip :title="help">
      <QuestionCircleOutlined class="field-help-icon" />
    </Tooltip>
  </span>
</template>
