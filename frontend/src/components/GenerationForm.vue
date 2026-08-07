<script setup lang="ts">
import { ref } from "vue"
import { Alert, Button, Card, Form, Input, InputNumber, message, Select, Space, Tooltip, Upload } from "ant-design-vue"
import { PlusOutlined, ThunderboltOutlined, UploadOutlined } from "@ant-design/icons-vue"
import { api, type GenerationRequest } from "../lib/api"
import { parseWorkflowFile } from "../lib/workflow"
import FieldLabel from "./FieldLabel.vue"

const props = defineProps<{
  form: GenerationRequest
  checkpoints: string[]
  motionModels?: string[]
  loraModels?: string[]
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
const fileInput = ref<HTMLInputElement | null>(null)
const referenceImageUploading = ref(false)
const referenceImagePreview = ref("")

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

async function onImportFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  try {
    const parsed = parseWorkflowFile(JSON.parse(await file.text()))
    if (parsed.mediaType !== props.mode) {
      message.warning(
        parsed.mediaType === "video"
          ? "这是视频工作流，请到视频生成页导入"
          : "这是图片工作流，请到图片生成页导入",
      )
      return
    }
    Object.assign(props.form, parsed.fields)
    message.success("已导入节点参数")
  } catch {
    message.error("导入失败：文件不是有效的节点工作流 JSON")
  }
}

async function onReferenceImageUpload(file: File) {
  referenceImageUploading.value = true
  try {
    const result = await api.uploadFile(file, "image")
    props.form.reference_image = result.name
    referenceImagePreview.value = URL.createObjectURL(file)
    message.success("参考图已上传")
  } catch (error) {
    message.error(error instanceof Error ? error.message : "参考图上传失败")
  } finally {
    referenceImageUploading.value = false
  }
  return false
}

function clearReferenceImage() {
  props.form.reference_image = ""
  referenceImagePreview.value = ""
}

function addLora() {
  if (!props.form.loras) props.form.loras = []
  if (props.form.loras.length >= 3) return
  props.form.loras.push({ name: "", model_strength: 1, clip_strength: 1 })
}

function removeLora(index: number) {
  props.form.loras.splice(index, 1)
}
</script>

<template>
  <Card title="生成参数" :bordered="false" class="generation-form-card">
    <template #extra>
      <Button size="small" @click="fileInput?.click()">
        <template #icon><UploadOutlined /></template>
        导入节点
      </Button>
      <input
        ref="fileInput"
        type="file"
        accept=".json,application/json"
        hidden
        @change="onImportFile"
      />
    </template>
    <Form layout="vertical">
      <div class="step-title">
        <span class="step-badge">1</span>
        <span class="step-name">模型加载</span>
        <span class="step-node">
          {{ mode === "video" ? "CheckpointLoaderSimple + ADE_AnimateDiffLoaderGen1" : "CheckpointLoaderSimple" }}
        </span>
      </div>
      <Form.Item
        class="step-field"
        :validate-status="blockedReason.includes('模型') || blockedReason.includes('ComfyUI') ? 'error' : undefined"
        :help="blockedReason.includes('模型') ? blockedReason : undefined"
      >
        <template #label>
          <FieldLabel
            label="模型"
            help="选择生成所用的 checkpoint 模型。加载时 ComfyUI 按文件名从自身模型目录读取：本地模式读取本机 ComfyUI 目录中的文件；远程模式只能加载远程 ComfyUI 上已存在的模型，本机目录文件不会被远程加载。"
          />
        </template>
        <Select v-model:value="form.checkpoint" placeholder="必填：请选择 checkpoint" :not-found-content="'暂无可用模型'">
          <Select.Option v-for="item in checkpoints" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
        </Select>
      </Form.Item>
      <Space v-if="mode === 'video'" class="form-row" align="start">
        <Form.Item class="form-main" required>
          <template #label>
            <FieldLabel label="运动模型" help="视频生成所需的 AnimateDiff 运动模型，需与 checkpoint 匹配使用。" />
          </template>
          <Select v-model:value="form.motion_model" placeholder="必填：选择 AnimateDiff 运动模型">
            <Select.Option v-for="item in motionModels ?? []" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item>
          <template #label>
            <FieldLabel label="Beta Schedule" help="AnimateDiff 的 beta 调度方案，不同运动模型推荐不同取值。" />
          </template>
          <Select v-model:value="form.beta_schedule">
            <Select.Option v-for="item in betaScheduleOptions" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
      </Space>

      <div v-if="mode === 'image'" class="step-title">
        <span class="step-badge">ref</span>
        <span class="step-name">参考图</span>
        <span class="step-node">LoadImage + VAEEncode</span>
      </div>
      <Form.Item v-if="mode === 'image'" class="step-field">
        <template #label>
          <FieldLabel
            label="参考图重绘"
            help="上传参考图后按图重绘：参考图作为采样起点，重绘幅度（denoise）越低越接近原图；输出尺寸跟随参考图，画布宽高将被忽略。"
          />
        </template>
        <Space wrap>
          <Upload
            :show-upload-list="false"
            accept="image/*"
            :before-upload="onReferenceImageUpload"
          >
            <Button :loading="referenceImageUploading">
              <template #icon><UploadOutlined /></template>
              上传参考图
            </Button>
          </Upload>
          <img
            v-if="referenceImagePreview"
            :src="referenceImagePreview"
            class="reference-image-preview"
            alt="参考图"
          />
          <span v-if="form.reference_image" class="field-help">{{ form.reference_image }}</span>
          <Button v-if="form.reference_image" size="small" @click="clearReferenceImage">
            移除
          </Button>
        </Space>
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">2</span>
        <span class="step-name">提示词</span>
        <span class="step-node">CLIPTextEncode</span>
      </div>
      <Form.Item
        required
        :validate-status="submissionAttempted && blockedReason === '请输入画面描述' ? 'error' : undefined"
        :help="submissionAttempted && blockedReason === '请输入画面描述' ? blockedReason : undefined"
      >
        <template #label>
          <FieldLabel label="画面描述" help="描述期望的画面内容，提示词越具体，生成结果越可控。" />
        </template>
        <Input.TextArea v-model:value="form.prompt" :rows="5" placeholder="例如：薄雾中的东方古城，电影级光影" />
      </Form.Item>
      <Form.Item>
        <template #label>
          <FieldLabel label="排除内容" help="不希望出现在画面中的内容，多个用逗号分隔。" />
        </template>
        <Input.TextArea v-model:value="form.negative_prompt" :rows="2" placeholder="模糊、低质量、文字" />
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">3</span>
        <span class="step-name">{{ mode === "video" ? "画布与时长" : "画布" }}</span>
        <span class="step-node">EmptyLatentImage</span>
      </div>
      <Space class="form-row" align="start">
        <Form.Item extra="64-4096，建议按 64 调整">
          <template #label>
            <FieldLabel label="宽度" help="输出图片的像素宽度，建议按 64 的倍数设置。" />
          </template>
          <InputNumber v-model:value="form.width" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item extra="64-4096，建议按 64 调整">
          <template #label>
            <FieldLabel label="高度" help="输出图片的像素高度，建议按 64 的倍数设置。" />
          </template>
          <InputNumber v-model:value="form.height" :min="64" :max="4096" :step="64" />
        </Form.Item>
        <Form.Item v-if="mode === 'video'" extra="2-120，越长越慢">
          <template #label>
            <FieldLabel label="帧数" help="视频总帧数，帧数越多视频越长、生成越慢。" />
          </template>
          <InputNumber v-model:value="form.frames" :min="2" :max="120" />
        </Form.Item>
        <Form.Item v-else>
          <template #label>
            <FieldLabel label="生成数量" help="一次任务生成的图片张数。" />
          </template>
          <InputNumber v-model:value="form.batch_size" :min="1" :max="8" />
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">lora</span>
        <span class="step-name">LoRA 叠加</span>
        <span class="step-node">LoraLoader</span>
      </div>
      <Form.Item class="step-field">
        <template #label>
          <FieldLabel
            label="LoRA 模型"
            help="最多叠加 3 个 LoRA，按顺序串联在 checkpoint 之后；model 强度影响画面结构，clip 强度影响语义跟随。"
          />
        </template>
        <Space direction="vertical" size="small" style="width: 100%">
          <div v-for="(lora, index) in form.loras ?? []" :key="index" class="lora-row">
            <Select
              v-model:value="lora.name"
              placeholder="选择 LoRA"
              :not-found-content="'暂无可用 LoRA'"
              style="min-width: 180px"
            >
              <Select.Option v-for="item in loraModels ?? []" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
            </Select>
            <Tooltip title="model 强度">
              <InputNumber v-model:value="lora.model_strength" :min="0" :max="4" :step="0.05" />
            </Tooltip>
            <Tooltip title="clip 强度">
              <InputNumber v-model:value="lora.clip_strength" :min="0" :max="4" :step="0.05" />
            </Tooltip>
            <Button size="small" @click="removeLora(index)">移除</Button>
          </div>
          <Button v-if="(form.loras ?? []).length < 3" size="small" @click="addLora">
            <template #icon><PlusOutlined /></template>
            添加 LoRA
          </Button>
        </Space>
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">4</span>
        <span class="step-name">采样器</span>
        <span class="step-node">KSampler</span>
      </div>
      <Space class="form-row" align="start">
        <Form.Item>
          <template #label>
            <FieldLabel label="随机种子" help="控制采样随机噪声，相同种子可复现相似结果；-1 表示每次随机。" />
          </template>
          <InputNumber v-model:value="form.seed" />
        </Form.Item>
        <Form.Item extra="1-150，越高越慢">
          <template #label>
            <FieldLabel label="步数" help="采样步数，越多细节越精细，耗时越长。" />
          </template>
          <InputNumber v-model:value="form.steps" :min="1" :max="150" />
        </Form.Item>
        <Form.Item extra="0-30，控制提示词强度">
          <template #label>
            <FieldLabel label="CFG" help="提示词引导强度，数值越高越贴近提示词，过高容易过饱和或失真。" />
          </template>
          <InputNumber v-model:value="form.cfg" :min="0" :max="30" :step="0.5" />
        </Form.Item>
      </Space>
      <Form.Item class="step-field" extra="0-1，文生图通常为 1，图生图/重绘时调低">
        <template #label>
          <FieldLabel label="重绘幅度 (denoise)" help="重绘比例：1 表示完全重绘，数值越低越接近输入原图。" />
        </template>
        <InputNumber v-model:value="form.denoise" :min="0" :max="1" :step="0.05" />
      </Form.Item>
      <Space class="form-row" align="start">
        <Form.Item class="form-main">
          <template #label>
            <FieldLabel label="采样器" help="采样算法，不同算法在画质、风格与速度上有差异。" />
          </template>
          <Select v-model:value="form.sampler">
            <Select.Option v-for="item in samplerOptions" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item class="form-main">
          <template #label>
            <FieldLabel label="调度器" help="步长调度方式，影响采样节奏与最终画质。" />
          </template>
          <Select v-model:value="form.scheduler">
            <Select.Option v-for="item in schedulerOptions" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
          </Select>
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">5</span>
        <span class="step-name">解码</span>
        <span class="step-node">VAEDecode</span>
      </div>
      <Form.Item class="step-field" extra="可选：不选则使用 checkpoint 自带 VAE（VAELoader）">
        <template #label>
          <FieldLabel label="VAE 模型" help="可选。不选时使用 checkpoint 自带的 VAE；选择后通过 VAELoader 单独加载。" />
        </template>
        <Select v-model:value="form.vae" placeholder="可选：默认使用 checkpoint 自带 VAE" allow-clear :not-found-content="'暂无可用 VAE'">
          <Select.Option v-for="item in vaeModels ?? []" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
        </Select>
      </Form.Item>

      <div class="step-title">
        <span class="step-badge">6</span>
        <span class="step-name">输出</span>
        <span class="step-node">{{ mode === "video" ? "SaveAnimatedWEBP" : "SaveImage" }}</span>
      </div>
      <Space v-if="mode === 'video'" class="form-row" align="start">
        <Form.Item extra="1-60">
          <template #label>
            <FieldLabel label="帧率 (fps)" help="视频播放帧率，越高画面越流畅、文件越大。" />
          </template>
          <InputNumber v-model:value="form.fps" :min="1" :max="60" />
        </Form.Item>
        <Form.Item extra="1-100">
          <template #label>
            <FieldLabel label="质量" help="WEBP 压缩质量，数值越高画质越好、文件越大。" />
          </template>
          <InputNumber v-model:value="form.quality" :min="1" :max="100" />
        </Form.Item>
        <Form.Item>
          <template #label>
            <FieldLabel label="无损" help="开启后不做有损压缩，画质无损但文件体积明显增大。" />
          </template>
          <a-switch v-model:checked="form.lossless" />
        </Form.Item>
        <Form.Item>
          <template #label>
            <FieldLabel label="压缩方式" help="WEBP 压缩策略：default 均衡、fastest 更快、slowest 体积更小。" />
          </template>
          <Select v-model:value="form.method">
            <Select.Option value="default" title="default">default</Select.Option>
            <Select.Option value="fastest" title="fastest">fastest</Select.Option>
            <Select.Option value="slowest" title="slowest">slowest</Select.Option>
          </Select>
        </Form.Item>
      </Space>
      <div v-else class="field-help step-field">结果图片将保存到 ComfyUI 输出目录（AIArtAgent 子目录）。</div>
      <Form.Item class="step-field" extra="可选：默认 AIArtAgent">
        <template #label>
          <FieldLabel label="输出文件名前缀" help="输出文件的名称前缀，用于区分生成结果，默认 AIArtAgent。" />
        </template>
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
