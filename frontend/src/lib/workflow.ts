import type { GenerationRequest } from "./api"

export type ParsedWorkflow = {
  mediaType: "image" | "video"
  fields: Partial<GenerationRequest>
}

type NodeInputs = Record<string, unknown>
type WorkflowNode = {
  id?: unknown
  type?: string
  class_type?: string
  inputs?: NodeInputs
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function nodeType(node: WorkflowNode): string {
  return typeof node.type === "string"
    ? node.type
    : typeof node.class_type === "string"
      ? node.class_type
      : ""
}

function nodeList(data: unknown): WorkflowNode[] {
  const root = isRecord(data) ? data : {}
  const container = isRecord(root.workflow) ? root.workflow : root
  if (Array.isArray(container.nodes)) {
    return container.nodes.filter(isRecord) as WorkflowNode[]
  }
  const list: WorkflowNode[] = []
  for (const key of Object.keys(container)) {
    const value = container[key]
    if (
      isRecord(value) &&
      (typeof value.type === "string" || typeof value.class_type === "string")
    ) {
      list.push(value as WorkflowNode)
    }
  }
  return list
}

function nodeInputs(node?: WorkflowNode): NodeInputs {
  return isRecord(node?.inputs) ? node.inputs : {}
}

function take(
  target: Partial<GenerationRequest>,
  source: NodeInputs,
  key: string,
  targetKey = key,
  convert?: (raw: unknown) => unknown,
) {
  const raw = source[key]
  if (raw === undefined || raw === null || raw === "") return
  ;(target as Record<string, unknown>)[targetKey] = convert ? convert(raw) : raw
}

function textBySamplerRef(nodes: WorkflowNode[], ref: unknown): string | undefined {
  if (!Array.isArray(ref)) return undefined
  const id = String(ref[0])
  const hit = nodes.find(node => String(node.id) === id)
  return hit ? String(nodeInputs(hit).text ?? "") : undefined
}

export function parseWorkflowFile(data: unknown): ParsedWorkflow {
  const nodes = nodeList(data)
  const byType = new Map<string, WorkflowNode[]>()
  for (const node of nodes) {
    const type = nodeType(node)
    if (!type) continue
    const list = byType.get(type) ?? []
    list.push(node)
    byType.set(type, list)
  }

  const sampler = nodeInputs(byType.get("KSampler")?.[0] ?? byType.get("ADE_AnimateDiffSampler")?.[0])
  const checkpoint = nodeInputs(byType.get("CheckpointLoaderSimple")?.[0])
  const latent = nodeInputs(byType.get("EmptyLatentImage")?.[0])
  const loader = nodeInputs(byType.get("ADE_AnimateDiffLoaderGen1")?.[0])
  const saveImage = nodeInputs(byType.get("SaveImage")?.[0])
  const saveVideo = nodeInputs(byType.get("SaveAnimatedWEBP")?.[0])
  const vaeLoader = nodeInputs(byType.get("VAELoader")?.[0])
  const clipNodes = byType.get("CLIPTextEncode") ?? []

  const fields: Partial<GenerationRequest> = {}
  const positiveText =
    textBySamplerRef(clipNodes, sampler.positive) ??
    (clipNodes[0] ? String(nodeInputs(clipNodes[0]).text ?? "") : undefined)
  const negativeText =
    textBySamplerRef(clipNodes, sampler.negative) ??
    (clipNodes[1] ? String(nodeInputs(clipNodes[1]).text ?? "") : undefined)
  if (positiveText !== undefined) fields.prompt = positiveText
  if (negativeText !== undefined) fields.negative_prompt = negativeText

  take(fields, checkpoint, "ckpt_name", "checkpoint")
  take(fields, latent, "width", "width", Number)
  take(fields, latent, "height", "height", Number)
  take(fields, sampler, "seed", "seed", Number)
  take(fields, sampler, "steps", "steps", Number)
  take(fields, sampler, "cfg", "cfg", Number)
  take(fields, sampler, "denoise", "denoise", Number)
  take(fields, loader, "model_name", "motion_model")
  take(fields, loader, "beta_schedule")
  take(fields, vaeLoader, "vae_name", "vae")
  take(fields, saveImage, "filename_prefix", "output_prefix")
  take(fields, saveVideo, "filename_prefix", "output_prefix")
  take(fields, saveVideo, "fps", "fps", Number)
  take(fields, saveVideo, "quality", "quality", Number)
  take(fields, saveVideo, "lossless", "lossless", Boolean)
  take(fields, saveVideo, "method", "method")

  const samplerName = sampler.sampler_name
  if (typeof samplerName === "string" && samplerName) fields.sampler = samplerName
  const scheduler = sampler.scheduler
  if (typeof scheduler === "string" && scheduler) fields.scheduler = scheduler

  const mediaType =
    byType.has("SaveAnimatedWEBP") || byType.has("ADE_AnimateDiffLoaderGen1")
      ? "video"
      : "image"
  const latentCount = latent.batch_size
  if (latentCount !== undefined && latentCount !== null && latentCount !== "") {
    if (mediaType === "video") fields.frames = Number(latentCount)
    else fields.batch_size = Number(latentCount)
  }

  return { mediaType, fields }
}
