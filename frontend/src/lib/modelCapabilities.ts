import type { CreationType, GenerationRequest, ModelItem } from "./api"

export const creationTypeLabels: Record<CreationType, string> = {
  text_to_image: "文生图",
  image_to_image: "图生图",
  text_to_video: "文生视频",
  image_to_video: "图生视频",
  video_to_video: "视频生视频",
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
