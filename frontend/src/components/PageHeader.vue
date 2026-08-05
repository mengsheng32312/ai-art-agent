<script setup lang="ts">
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <header class="page-heading">
    <h1 class="page-title">{{ title }}</h1>
    <p class="page-description">{{ description }}</p>
  </header>
</template>
