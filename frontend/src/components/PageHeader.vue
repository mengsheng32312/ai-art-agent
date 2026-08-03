<script setup lang="ts">
import { PageHeader } from "ant-design-vue"

defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <PageHeader class="page-heading" :title="title" :sub-title="description" />
</template>
