<script setup lang="ts">
import { computed, h } from "vue"
import { Layout, Menu, Tag } from "ant-design-vue"
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  AppstoreOutlined,
  PictureOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  VideoCameraOutlined,
} from "@ant-design/icons-vue"
import type { Page } from "../types"

const props = defineProps<{
  page: Page
  collapsed: boolean
  connected: boolean
}>()

const emit = defineEmits<{
  "update:page": [page: Page]
}>()

// Ant Design Menu keys mirror the app page type.
const selectedKeys = computed(() => [props.page])
const menuItems = [
  { key: "generate", icon: () => h(PictureOutlined), label: "图片生成" },
  { key: "video", icon: () => h(VideoCameraOutlined), label: "视频生成" },
  { key: "models", icon: () => h(AppstoreOutlined), label: "模型管理" },
  { key: "history", icon: () => h(HistoryOutlined), label: "历史记录" },
  { key: "settings", icon: () => h(SettingOutlined), label: "连接设置" },
]
</script>

<template>
  <Layout.Sider class="app-sider" theme="light" :width="256" :collapsed-width="80" :collapsed="collapsed">
    <div class="sider-brand" :class="{ collapsed }">
      <div class="brand-logo">
        <ThunderboltOutlined />
      </div>
      <div v-if="!collapsed" class="brand-text">
        <strong>AI Art Agent</strong>
        <span>创作工作台</span>
      </div>
    </div>

    <Menu
      mode="inline"
      :selected-keys="selectedKeys"
      :items="menuItems"
      @click="event => emit('update:page', event.key as Page)"
    />

    <div class="sider-status" :class="{ collapsed }">
      <Tag :color="connected ? 'success' : 'default'">
        <CheckCircleOutlined v-if="connected" />
        <CloseCircleOutlined v-else />
        {{ collapsed ? "" : connected ? "ComfyUI 已连接" : "ComfyUI 未连接" }}
      </Tag>
    </div>
  </Layout.Sider>
</template>
