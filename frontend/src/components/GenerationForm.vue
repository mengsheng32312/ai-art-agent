<script setup lang="ts">
import { computed, ref, watch } from "vue"
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Form,
  Input,
  InputNumber,
  message,
  Segmented,
  Select,
  Space,
  Switch,
  Tag,
  Tooltip,
  Upload,
  type UploadFile,
} from "ant-design-vue"
import { PlusOutlined, ThunderboltOutlined, UploadOutlined } from "@ant-design/icons-vue"
import {
  api,
  type ContentTag,
  type CreationType,
  type GenerationRequest,
  type ModelItem,
} from "../lib/api"
import {
  applyCreationType,
  contentTagLabels,
  creationTypeLabels,
  filterModelsForContent,
} from "../lib/modelCapabilities"
import { parseWorkflowFile } from "../lib/workflow"
import FieldLabel from "./FieldLabel.vue"

const props = defineProps<{
  form: GenerationRequest
  models: ModelItem[]
  motionModels?: string[]
  loraModels?: string[]
  controlnetModels?: string[]
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
const uploading = ref(false)
const pendingFiles = ref<Record<string, File>>({})
const referenceImageFiles = ref<UploadFile[]>([])
const controlnetFiles = ref<UploadFile[]>([])
const referenceVideoFiles = ref<UploadFile[]>([])
const selectedContentTag = ref<ContentTag>("general")
const beginnerMode = ref(true)

const contentTagOptions = Object.entries(contentTagLabels).map(([value, label]) => ({
  label,
  value: value as ContentTag,
}))

const creationTypeOptions = computed(() =>
  props.mode === "image"
    ? [
        { label: "文生图", value: "text_to_image" },
        { label: "图生图", value: "image_to_image" },
      ]
    : [
        { label: "文生视频", value: "text_to_video" },
        { label: "图生视频", value: "image_to_video" },
        { label: "视频生视频", value: "video_to_video" },
      ],
)
const selectedModel = computed(() =>
  props.models.find(item => item.filename === props.form.checkpoint),
)
const filteredModels = computed(() =>
  filterModelsForContent(
    props.models,
    props.form.creation_type,
    selectedContentTag.value,
    beginnerMode.value,
  ),
)
const filteredModelOptions = computed(() =>
  filteredModels.value.map(item => ({
    label: `${item.name}（${item.filename}） · ${item.capability_profile.content_tags
      .map(tag => contentTagLabels[tag])
      .join("/")}`,
    value: item.filename,
    title: item.filename,
  })),
)
watch(
  filteredModels,
  models => {
    if (
      props.form.checkpoint
      && !models.some(item => item.filename === props.form.checkpoint)
    ) {
      props.form.checkpoint = ""
    }
  },
  { flush: "sync" },
)
const selectedModelComponents = computed(() => {
  const components = selectedModel.value?.capability_profile.required_components[
    props.form.creation_type
  ] ?? []
  return components.length ? components.join("、") : "无额外组件"
})
const selectedRecommendedParams = computed(() =>
  Object.entries(
    selectedModel.value?.capability_profile.recommended_params[props.form.creation_type] ?? {},
  )
    .map(([key, value]) => `${key}：${value}`)
    .join("，"),
)

function changeCreationType(value: string | number) {
  applyCreationType(props.form, value as CreationType, props.models)
}

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

async function submit() {
  if (uploading.value || props.busy) return
  const keys = Object.keys(pendingFiles.value)
  if (!keys.length) {
    emit("generate")
    return
  }
  uploading.value = true
  try {
    for (const key of keys) {
      const file = pendingFiles.value[key]
      const kind = key === "reference_video" ? "video" : "image"
      const result = await api.uploadFile(file, kind)
      if (key === "reference_image") {
        props.form.reference_image = result.name
      } else if (key === "controlnet") {
        if (!props.form.controlnet) {
          props.form.controlnet = {
            model: "",
            preprocessor: "canny",
            image: "",
            strength: 1,
            start_percent: 0,
            end_percent: 1,
          }
        }
        props.form.controlnet.image = result.name
      } else {
        props.form.reference_video = result.name
      }
    }
    pendingFiles.value = {}
    emit("generate")
  } catch (error) {
    message.error(error instanceof Error ? error.message : "参考文件上传失败")
  } finally {
    uploading.value = false
  }
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
    message.success("已导入工作流参数")
  } catch {
    message.error("导入失败：文件不是有效的工作流 JSON")
  }
}

function selectReferenceImage(file: File) {
  pendingFiles.value["reference_image"] = file
  props.form.reference_image = file.name
  referenceImageFiles.value = [
    {
      uid: "reference_image",
      name: file.name,
      status: "done",
      url: URL.createObjectURL(file),
    },
  ]
  return false
}

function clearReferenceImage() {
  delete pendingFiles.value["reference_image"]
  props.form.reference_image = ""
  referenceImageFiles.value = []
}

function addLora() {
  if (!props.form.loras) props.form.loras = []
  if (props.form.loras.length >= 3) return
  props.form.loras.push({ name: "", model_strength: 1, clip_strength: 1 })
}

function removeLora(index: number) {
  props.form.loras.splice(index, 1)
}

const preprocessorOptions = [
  { label: "Canny 边缘", value: "canny" },
  { label: "深度图", value: "depth" },
  { label: "线稿", value: "lineart" },
  { label: "姿态 OpenPose", value: "openpose" },
  { label: "原始图直传", value: "none" },
]

function selectControlnetImage(file: File) {
  if (!props.form.controlnet) {
    props.form.controlnet = {
      model: "",
      preprocessor: "canny",
      image: file.name,
      strength: 1,
      start_percent: 0,
      end_percent: 1,
    }
  } else {
    props.form.controlnet.image = file.name
  }
  pendingFiles.value["controlnet"] = file
  controlnetFiles.value = [
    {
      uid: "controlnet",
      name: file.name,
      status: "done",
      url: URL.createObjectURL(file),
    },
  ]
  return false
}

function clearControlnet() {
  delete pendingFiles.value["controlnet"]
  props.form.controlnet = null
  controlnetFiles.value = []
}

function toggleHires(enabled: boolean) {
  props.form.hires = enabled
    ? { scale: 2, steps: 12, denoise: 0.5 }
    : null
}

function selectReferenceVideo(file: File) {
  pendingFiles.value["reference_video"] = file
  props.form.reference_video = file.name
  referenceVideoFiles.value = [
    {
      uid: "reference_video",
      name: file.name,
      status: "done",
      url: URL.createObjectURL(file),
    },
  ]
  return false
}

function clearReferenceVideo() {
  delete pendingFiles.value["reference_video"]
  props.form.reference_video = ""
  referenceVideoFiles.value = []
}
</script>

<template>
  <Card title="生成参数" :bordered="false" class="generation-form-card">
    <template #extra>
      <Button size="small" @click="fileInput?.click()">
        <template #icon><UploadOutlined /></template>
        导入工作流
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
      <Form.Item class="step-field">
        <template #label>
          <FieldLabel
            label="创作任务"
            :help="mode === 'image' ? '先选择文生图或图生图，模型列表会自动筛选。' : '先选择文生视频、图生视频或视频生视频，模型列表会自动筛选。'"
          />
        </template>
        <Segmented
          data-testid="creation-type-selector"
          :value="form.creation_type"
          :options="creationTypeOptions"
          @change="changeCreationType"
        />
      </Form.Item>

      <Space class="form-row" align="start" wrap>
        <Form.Item class="form-main step-field">
          <template #label>
            <FieldLabel
              label="想生成的内容"
              help="选择大致题材后，新手选模会优先展示更匹配的模型；选择通用时不限制题材。"
            />
          </template>
          <div data-testid="content-category-selector">
            <Select v-model:value="selectedContentTag" :options="contentTagOptions" />
          </div>
        </Form.Item>
        <Form.Item class="step-field">
          <template #label>
            <FieldLabel
              label="新手选模"
              help="开启后隐藏与所选题材不匹配的专用模型，通用模型仍会显示。"
            />
          </template>
          <Space data-testid="beginner-model-switch">
            <Switch v-model:checked="beginnerMode" />
            <span>{{ beginnerMode ? "已开启" : "已关闭" }}</span>
          </Space>
        </Form.Item>
      </Space>

      <div class="step-title">
        <span class="step-badge">1</span>
        <span class="step-name">模型加载</span>
        <span class="step-node">
          {{ mode === "video" ? "CheckpointLoaderSimple + ADE_AnimateDiffLoaderGen1" : "CheckpointLoaderSimple" }}
        </span>
      </div>
      <Form.Item
        class="step-field"
        :validate-status="submissionAttempted && (blockedReason.includes('模型') || blockedReason.includes('ComfyUI')) ? 'error' : undefined"
        :help="submissionAttempted && blockedReason.includes('模型') ? blockedReason : undefined"
      >
        <template #label>
          <FieldLabel
            label="模型"
            help="选择生成所用的 checkpoint 模型。加载时 ComfyUI 按文件名从自身模型目录读取：本地模式读取本机 ComfyUI 目录中的文件；远程模式只能加载远程 ComfyUI 上已存在的模型，本机目录文件不会被远程加载。"
          />
        </template>
        <div data-testid="model-selector">
          <Select
            v-model:value="form.checkpoint"
            :options="filteredModelOptions"
            placeholder="必填：请选择兼容模型"
            :not-found-content="beginnerMode && selectedContentTag !== 'general'
              ? '当前内容分类暂无合适模型，可关闭新手选模查看全部兼容模型'
              : '当前任务暂无兼容模型'"
          />
        </div>
      </Form.Item>
      <Alert
        v-if="selectedModel"
        class="step-field"
        type="info"
        show-icon
        :message="selectedModel.capability_profile.description_zh"
      >
        <template #description>
          <Space wrap>
            <Tag v-for="capability in selectedModel.capability_profile.capabilities" :key="capability">
              {{ creationTypeLabels[capability] }}
            </Tag>
            <span>必需组件：{{ selectedModelComponents }}</span>
            <span v-if="selectedRecommendedParams">推荐参数：{{ selectedRecommendedParams }}</span>
          </Space>
        </template>
      </Alert>
      <Space v-if="form.creation_type === 'text_to_video'" class="form-row" align="start">
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

      <div v-if="form.creation_type === 'image_to_image' || form.creation_type === 'image_to_video'" class="step-title">
        <span class="step-badge">ref</span>
        <span class="step-name">参考图</span>
        <span class="step-node">{{ form.creation_type === "image_to_image" ? "LoadImage + VAEEncode" : "WanImageToVideo 首帧" }}</span>
      </div>
      <Form.Item v-if="form.creation_type === 'image_to_image' || form.creation_type === 'image_to_video'" class="step-field" required>
        <template #label>
          <FieldLabel
            label="参考图（必填）"
            :help="form.creation_type === 'image_to_image'
              ? '上传参考图后按图重绘：参考图作为采样起点，重绘幅度（denoise）越低越接近原图；输出尺寸跟随参考图，画布宽高将被忽略。'
              : '上传一张图作为视频首帧，模型将推断后续运动（Wan I2V）。'"
          />
        </template>
        <Space direction="vertical" size="small" style="width: 100%">
          <Upload
            accept="image/*"
            :show-upload-list="false"
            :before-upload="selectReferenceImage"
          >
            <Button>
              <template #icon><UploadOutlined /></template>
              {{ referenceImageFiles.length ? "更换参考图" : "选择参考图" }}
            </Button>
          </Upload>
          <div v-if="referenceImageFiles[0]" class="reference-media-card">
            <img
              :src="referenceImageFiles[0].url"
              :alt="referenceImageFiles[0].name"
              class="reference-media-preview"
            />
            <div class="reference-media-meta">
              <strong class="reference-media-name" :title="referenceImageFiles[0].name">
                {{ referenceImageFiles[0].name }}
              </strong>
              <span class="field-help">预览已加载，生成时上传到 ComfyUI</span>
              <Button size="small" @click="clearReferenceImage">移除</Button>
            </div>
          </div>
        </Space>
      </Form.Item>

      <div v-if="form.creation_type === 'video_to_video'" class="step-title">
        <span class="step-badge">refv</span>
        <span class="step-name">参考视频</span>
        <span class="step-node">LoadVideo 首尾帧</span>
      </div>
      <Form.Item v-if="form.creation_type === 'video_to_video'" class="step-field" required>
        <template #label>
          <FieldLabel
            label="参考视频"
            help="上传参考视频，取其首尾帧约束输出视频的运动；建议帧数不少于生成帧数（Wan V2V）。"
          />
        </template>
        <Space direction="vertical" size="small" style="width: 100%">
          <Upload
            accept="video/*"
            :show-upload-list="false"
            :before-upload="selectReferenceVideo"
          >
            <Button>
              <template #icon><UploadOutlined /></template>
              {{ referenceVideoFiles.length ? "更换参考视频" : "选择参考视频" }}
            </Button>
          </Upload>
          <div v-if="referenceVideoFiles[0]" class="reference-media-card">
            <video
              :src="referenceVideoFiles[0].url"
              class="reference-media-preview"
              controls
              muted
            />
            <div class="reference-media-meta">
              <strong class="reference-media-name" :title="referenceVideoFiles[0].name">
                {{ referenceVideoFiles[0].name }}
              </strong>
              <span class="field-help">预览已加载，生成时上传到 ComfyUI</span>
              <Button size="small" @click="clearReferenceVideo">移除</Button>
            </div>
          </div>
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
            <span class="lora-label">{{ index + 1 }}# LoRA</span>
            <Select
              v-model:value="lora.name"
              placeholder="选择 LoRA"
              :not-found-content="'暂无可用 LoRA'"
              style="min-width: 180px"
            >
              <Select.Option v-for="item in loraModels ?? []" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
            </Select>
            <span class="lora-label">Model</span>
            <InputNumber v-model:value="lora.model_strength" :min="0" :max="4" :step="0.05" />
            <span class="lora-label">Clip</span>
            <InputNumber v-model:value="lora.clip_strength" :min="0" :max="4" :step="0.05" />
            <Button size="small" @click="removeLora(index)">移除</Button>
          </div>
          <Button v-if="(form.loras ?? []).length < 3" size="small" @click="addLora">
            <template #icon><PlusOutlined /></template>
            添加 LoRA
          </Button>
        </Space>
      </Form.Item>

      <div v-if="mode === 'image'" class="step-title">
        <span class="step-badge">cn</span>
        <span class="step-name">ControlNet 控制</span>
        <span class="step-node">ControlNetApplyAdvanced</span>
      </div>
      <Form.Item
        v-if="mode === 'image'"
        class="step-field"
        :validate-status="submissionAttempted && blockedReason.includes('ControlNet') ? 'error' : undefined"
        :help="submissionAttempted && blockedReason.includes('ControlNet') ? blockedReason : undefined"
      >
        <template #label>
          <FieldLabel
            label="ControlNet"
            help="上传条件图并选择控制模型：Canny 线稿约束构图、深度图约束空间关系、姿态约束人物动作。strength 越高约束越强，start/end 控制生效的采样区间。"
          />
        </template>
        <Space direction="vertical" size="small" style="width: 100%">
          <Upload
            accept="image/*"
            :show-upload-list="false"
            :before-upload="selectControlnetImage"
          >
            <Button>
              <template #icon><UploadOutlined /></template>
              {{ controlnetFiles.length ? "更换条件图" : "选择条件图" }}
            </Button>
          </Upload>
          <div v-if="controlnetFiles[0]" class="reference-media-card">
            <img
              :src="controlnetFiles[0].url"
              :alt="controlnetFiles[0].name"
              class="reference-media-preview"
            />
            <div class="reference-media-meta">
              <strong class="reference-media-name" :title="controlnetFiles[0].name">
                {{ controlnetFiles[0].name }}
              </strong>
              <span class="field-help">预览已加载，生成时上传到 ComfyUI</span>
              <Button size="small" @click="clearControlnet">移除</Button>
            </div>
          </div>
          <Space v-if="form.controlnet" wrap>
            <Select v-model:value="form.controlnet.model" placeholder="选择 ControlNet 模型" style="min-width: 200px">
              <Select.Option v-for="item in controlnetModels ?? []" :key="item" :value="item" :title="item">{{ item }}</Select.Option>
            </Select>
            <Select v-model:value="form.controlnet.preprocessor" :options="preprocessorOptions" style="min-width: 130px" />
            <span class="lora-label">强度</span>
            <InputNumber v-model:value="form.controlnet.strength" :min="0" :max="4" :step="0.05" />
            <span class="lora-label">开始</span>
            <InputNumber v-model:value="form.controlnet.start_percent" :min="0" :max="1" :step="0.05" />
            <span class="lora-label">结束</span>
            <InputNumber v-model:value="form.controlnet.end_percent" :min="0" :max="1" :step="0.05" />
          </Space>
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

      <div v-if="mode === 'image'" class="step-title">
        <span class="step-badge">hr</span>
        <span class="step-name">Hires fix 高清放大</span>
        <span class="step-node">LatentUpscale + KSampler</span>
      </div>
      <Form.Item v-if="mode === 'image'" class="step-field">
        <template #label>
          <FieldLabel
            label="Hires fix"
            help="先按缩小尺寸采样，再放大 latent 用第二次采样精修细节。放大倍率越高耗时越长，二次 denoise 建议 0.3-0.6。"
          />
        </template>
        <Space wrap>
          <Checkbox
            :checked="Boolean(form.hires)"
            @change="event => toggleHires(Boolean(event.target.checked))"
          >
            启用高清放大
          </Checkbox>
          <template v-if="form.hires">
            <span class="lora-label">倍率</span>
            <InputNumber v-model:value="form.hires.scale" :min="1" :max="4" :step="0.25" />
            <span class="lora-label">步数</span>
            <InputNumber v-model:value="form.hires.steps" :min="1" :max="60" />
            <span class="lora-label">Denoise</span>
            <InputNumber v-model:value="form.hires.denoise" :min="0" :max="1" :step="0.05" />
          </template>
        </Space>
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
          <Switch v-model:checked="form.lossless" />
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
        <Button type="primary" block size="large" :loading="busy || uploading" :disabled="!canGenerate || uploading" @click="submit">
          <template #icon><ThunderboltOutlined /></template>
          {{ uploading ? "正在上传参考文件" : busy ? "正在提交" : mode === "video" ? "开始生成视频" : "开始生成" }}
        </Button>
      </Tooltip>

      <Alert v-if="notice" class="form-notice" :type="noticeType" show-icon :message="notice" />
    </Form>
  </Card>
</template>
