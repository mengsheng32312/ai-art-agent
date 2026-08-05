<script setup lang="ts">
import { Alert, Button, Card, Form, Input, InputNumber, Select, Space, Tooltip } from "ant-design-vue"
import { ThunderboltOutlined } from "@ant-design/icons-vue"
import type { GenerationRequest } from "../lib/api"

const props = defineProps<{
  form: GenerationRequest
  checkpoints: string[]
  motionModels?: string[]
  vaeModels?: string[]
  canGenerate: boolean
  blockedReason: string
  submissionAttempted: boolean
  busy: boolean
  notice: string
  noticeType: "info" | "success" | "error"
  mode: "image" | "video"
}>()

const emit = defineEmits<{ generate: []; goModels: [] }>()

const samplerOptions = [
  "euler",
  "euler_cfg_pp",
  "euler_ancestral",
  "euler_ancestral_cfg_pp",
  "heun",
  "heunpp2",
  "exp_heun_2_x0",
  "exp_heun_2_x0_sde",
  "dpm_2",
  "dpm_2_ancestral",
  "lms",
  "dpm_fast",
  "dpm_adaptive",
  "dpmpp_2s_ancestral",
  "dpmpp_2s_ancestral_cfg_pp",
  "dpmpp_sde",
  "dpmpp_sde_gpu",
  "dpmpp_2m",
  "dpmpp_2m_cfg_pp",
  "dpmpp_2m_sde",
  "dpmpp_2m_sde_gpu",
  "dpmpp_2m_sde_heun",
  "dpmpp_2m_sde_heun_gpu",
  "dpmpp_3m_sde",
  "dpmpp_3m_sde_gpu",
  "ddpm",
  "lcm",
  "ipndm",
  "ipndm_v",
  "deis",
  "res_multistep",
  "res_multistep_cfg_pp",
  "res_multistep_ancestral",
  "res_multistep_ancestral_cfg_pp",
  "gradient_estimation",
  "gradient_estimation_cfg_pp",
  "er_sde",
  "seeds_2",
  "seeds_3",
  "sa_solver",
  "sa_solver_pece",
  "ddim",
  "uni_pc",
  "uni_pc_bh2",
]

const schedulerOptions = [
  "simple",
  "sgm_uniform",
  "karras",
  "exponential",
  "ddim_uniform",
  "beta",
  "normal",
  "linear_quadratic",
  "kl_optimal",
]

const betaScheduleOptions = [
  "autoselect",
  "sqrt_linear (AnimateDiff)",
  "linear (AnimateDiff-SDXL)",
  "linear (HotshotXL/default)",
  "avg(sqrt_linear,linear)",
  "lcm avg(sqrt_linear,linear)",
  "lcm",
  "lcm[100_ots]",
  "lcm >> sqrt_linear",
  "sqrt",
  "cosine",
  "squaredcos_cap_v2",
]

function submit() {
  emit("generate")
}
</script>

<template>
  <Card title="生成参数" :bordered="false">
    <Form layout="vertical">
      <div class="step-title">
        <span class="step-badge">1</span>
        <span class="step-name">模型加载</span>
        <span class="step-node">
          {{ mode === "video" ? "CheckpointLoaderSimple + ADE_AnimateDiffLoaderGen1" : "CheckpointLoaderSimple" }}
        </span>
      </div>
      <Form.Item
        label="模型"
        class="step-field"
        :validate-status="blockedReason.includes('模型') || blockedReason.includes('ComfyUI') ? 'error' : undefined"
        :help="blockedReason.includes('模型') ? blockedReason : undefined"
      >
        <Select v-model:value="form.checkpoint" placeholder="必填：请选择 checkpoint" :not-found-content="'暂无可用模型'">
          <Select.Option v-for="item in checkpoints" :key="item" :value="item">{{ item }}</Select.Option>
        </Select>
      </Form.Item>
      <Space v-if="mode === 'video'" class="form-row" align="start">
        <Form.Item label="运动模型" class="form-main" required>
          <Select v-model:value="form.motion_model" placeholder="必填：选择 AnimateDiff 运动模型">
            <Select.Option v-for="item in motionModels ?? []" :key="item" :value="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="Beta Schedule">
          <Select v-model:value="form.beta_schedule">
            <Select.Option v-for="item in betaScheduleOptions" :key="item" :value="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">2</span>
        <span class="step-name">提示词</span>
        <span class="step-node">CLIPTextEncode</span>
      </div>
      <Form.Item
        label="画面描述"
        required
        :validate-status="submissionAttempted && blockedReason === '请输入画面描述' ? 'error' : undefined"
        :help="submissionAttempted && blockedReason === '请输入画面描述' ? blockedReason : undefined"
      >
        <Input.TextArea v-model:value="form.prompt" :rows="5" placeholder="例如：薄雾中的东方古城，电影级光影" />
      </Form.Item>
      <Form.Item label="排除内容">
        <Input.TextArea v-model:value="form.negative_prompt" :rows="2" placeholder="模糊、低质量、文字" />
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">3</span>
        <span class="step-name">{{ mode === "video" ? "画布与时长" : "画布" }}</span>
        <span class="step-node">EmptyLatentImage</span>
      </div>
      <Space class="form-row" align="start">
        <Form.Item label="宽度" extra="64-4096，建议按 64 调整">
          <InputNumber v-model:value="form.width" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item label="高度" extra="64-4096，建议按 64 调整">
          <InputNumber v-model:value="form.height" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item v-if="mode === 'video'" label="帧数" extra="2-120，越长越慢">
          <InputNumber v-model:value="form.frames" :min="2" :max="120" />
        </Form.Item>
        <Form.Item v-else label="生成数量">
          <InputNumber v-model:value="form.batch_size" :min="1" :max="8" />
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">4</span>
        <span class="step-name">采样器</span>
        <span class="step-node">KSampler</span>
      </div>
      <Space class="form-row" align="start">
        <Form.Item label="随机种子">
          <InputNumber v-model:value="form.seed" />
        </Form.Item>
        <Form.Item label="步数" extra="1-150，越高越慢">
          <InputNumber v-model:value="form.steps" :min="1" :max="150" />
        </Form.Item>
        <Form.Item label="CFG" extra="0-30，控制提示词强度">
          <InputNumber v-model:value="form.cfg" :min="0" :max="30" :step="0.5" />
        </Form.Item>
      </Space>
      <Form.Item label="重绘幅度 (denoise)" class="step-field" extra="0-1，文生图通常为 1，图生图/重绘时调低">
        <InputNumber v-model:value="form.denoise" :min="0" :max="1" :step="0.05" />
      </Form.Item>
      <Space class="form-row" align="start">
        <Form.Item label="采样器" class="form-main">
          <Select v-model:value="form.sampler">
            <Select.Option v-for="item in samplerOptions" :key="item" :value="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="调度器" class="form-main">
          <Select v-model:value="form.scheduler">
            <Select.Option v-for="item in schedulerOptions" :key="item" :value="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">5</span>
        <span class="step-name">解码</span>
        <span class="step-node">VAEDecode</span>
      </div>
      <Form.Item label="VAE 模型" class="step-field" extra="可选：不选则使用 checkpoint 自带 VAE（VAELoader）">
        <Select v-model:value="form.vae" placeholder="可选：默认使用 checkpoint 自带 VAE" allow-clear :not-found-content="'暂无可用 VAE'">
          <Select.Option v-for="item in vaeModels ?? []" :key="item" :value="item">{{ item }}</Select.Option>
        </Select>
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">6</span>
        <span class="step-name">输出</span>
        <span class="step-node">{{ mode === "video" ? "SaveAnimatedWEBP" : "SaveImage" }}</span>
      </div>
      <Space v-if="mode === 'video'" class="form-row" align="start">
        <Form.Item label="帧率 (fps)" extra="1-60">
          <InputNumber v-model:value="form.fps" :min="1" :max="60" />
        </Form.Item>
        <Form.Item label="质量" extra="1-100">
          <InputNumber v-model:value="form.quality" :min="1" :max="100" />
        </Form.Item>
        <Form.Item label="无损">
          <a-switch v-model:checked="form.lossless" />
        </Form.Item>
        <Form.Item label="压缩方式">
          <Select v-model:value="form.method">
            <Select.Option value="default">default</Select.Option>
            <Select.Option value="fastest">fastest</Select.Option>
            <Select.Option value="slowest">slowest</Select.Option>
          </Select>
        </Form.Item>
      </Space>
      <div v-else class="field-help step-field">结果图片将保存到 ComfyUI 输出目录（AIArtAgent 子目录）。</div>
      <Form.Item label="输出文件名前缀" class="step-field" extra="可选：默认 AIArtAgent">
        <Input v-model:value="form.output_prefix" placeholder="AIArtAgent" />
      </Form.Item>

      <Alert v-if="submissionAttempted && blockedReason && !busy" class="form-notice" type="warning" show-icon :message="blockedReason" />

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
          {{ busy ? "正在提交" : mode === "video" ? "开始生成视频" : "开始生成" }}
        </Button>
      </Tooltip>

      <Alert v-if="notice" class="form-notice" :type="noticeType" show-icon :message="notice" />
    </Form>
  </Card>
</template>
