<script setup lang="ts">
import { Alert, Card, Col, Empty, Row, Space, Spin, Tag } from "ant-design-vue"
import type { ModelItem } from "../lib/api"

defineProps<{
  downloadingModels: ModelItem[]
}>()

function kindText(kind: ModelItem["kind"]) {
  return {
    checkpoint: "Checkpoint",
    lora: "LoRA",
    controlnet: "ControlNet",
    vae: "VAE",
    other: "其他",
  }[kind]
}
</script>

<template>
  <div class="page-workspace page-scroll">
    <Card :bordered="false" class="model-toolbar">
      <div class="model-toolbar-content">
        <div class="model-toolbar-status">
          <span class="field-help">显示当前正在下载到远程设备的模型</span>
          <div class="model-toolbar-stats">
            <span class="model-stat-item">下载中：{{ downloadingModels.length }}</span>
          </div>
        </div>
      </div>
    </Card>

    <Alert
      class="model-section"
      type="info"
      show-icon
      message="下载任务串行执行"
      description="完成一个模型下载后才会开始下一个。在模型管理页可以继续给其他模型添加下载任务。"
    />

    <Card :bordered="false" class="model-section">
      <template #title>正在下载</template>
      <Empty
        v-if="!downloadingModels.length"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        description="当前没有正在下载的模型"
      />
      <Row v-else :gutter="[12, 12]" class="model-list-row">
        <Col v-for="item in downloadingModels" :key="item.id" :xs="24">
          <Card :bordered="false" class="model-card">
            <template #title>
              <Space>
                <span :title="item.name">{{ item.name }}</span>
                <Tag>{{ kindText(item.kind) }}</Tag>
                <Tag color="processing">
                  <Spin size="small" />
                  下载中
                </Tag>
              </Space>
            </template>
            <Space direction="vertical" size="middle" class="model-content">
              <div class="model-preview">
                <strong>{{ kindText(item.kind) }}</strong>
                <span>{{ item.size_label || "远程下载" }}</span>
              </div>
              <div class="model-file" :title="item.filename">{{ item.filename }}</div>
            </Space>
          </Card>
        </Col>
      </Row>
    </Card>
  </div>
</template>
