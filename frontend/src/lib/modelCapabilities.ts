import type { ContentTag, CreationType, GenerationRequest, ModelItem } from "./api"

export const creationTypeLabels: Record<CreationType, string> = {
  text_to_image: "文生图",
  image_to_image: "图生图",
  text_to_video: "文生视频",
  image_to_video: "图生视频",
  video_to_video: "视频生视频",
}

export const contentTagLabels: Record<ContentTag, string> = {
  portrait: "人物",
  landscape: "风景",
  anime: "动漫",
  product: "产品/静物",
  architecture: "建筑/室内",
  general: "通用",
}

export function filterModelsForCreationType(
  models: ModelItem[],
  creationType: CreationType,
): ModelItem[] {
  return models.filter(
    item =>
      item.kind === "checkpoint" &&
      item.capability_profile.confirmed &&
      item.capability_profile.capabilities.includes(creationType),
  )
}

export function filterModelsForContent(
  models: ModelItem[],
  creationType: CreationType,
  contentTag: ContentTag,
  beginnerMode: boolean,
): ModelItem[] {
  const compatible = filterModelsForCreationType(models, creationType)
  if (!beginnerMode || contentTag === "general") return compatible
  return compatible
    .filter(item =>
      item.capability_profile.content_tags.includes(contentTag)
      || item.capability_profile.content_tags.includes("general"),
    )
    .sort(
      (a, b) => Number(b.capability_profile.content_tags.includes(contentTag))
        - Number(a.capability_profile.content_tags.includes(contentTag)),
    )
}

export function applyCreationType(
  request: GenerationRequest,
  creationType: CreationType,
  models: ModelItem[],
): void {
  request.creation_type = creationType
  request.media_type = creationType.endsWith("_video") ? "video" : "image"
  const videoModes: Partial<Record<CreationType, GenerationRequest["video_mode"]>> = {
    text_to_video: "t2v",
    image_to_video: "i2v",
    video_to_video: "v2v",
  }
  request.video_mode = videoModes[creationType] ?? "t2v"

  if (creationType !== "image_to_image" && creationType !== "image_to_video") {
    request.reference_image = ""
  }
  if (creationType !== "video_to_video") {
    request.reference_video = ""
  }

  const selected = models.find(item => item.filename === request.checkpoint)
  if (
    selected &&
    (!selected.capability_profile.confirmed ||
      !selected.capability_profile.capabilities.includes(creationType))
  ) {
    request.checkpoint = ""
  }
}
