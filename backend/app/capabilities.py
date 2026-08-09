import json
from pathlib import Path

from .schemas import ContentTag, ModelCapabilityProfile, ModelItem


PENDING_DESCRIPTION = "暂未识别该模型的生成能力，请先确认用途。"
CONTENT_KEYWORDS: dict[ContentTag, tuple[str, ...]] = {
    "portrait": ("portrait", "face", "character", "人物", "人像", "肖像"),
    "landscape": ("landscape", "scenery", "scenic", "nature", "风景", "景观", "自然"),
    "anime": ("anime", "manga", "cartoon", "comic", "动漫", "二次元", "漫画"),
    "product": ("product", "still life", "商品", "产品", "静物"),
    "architecture": ("architecture", "architectural", "interior", "building", "room", "建筑", "室内", "家装"),
}


def infer_content_tags(item: ModelItem) -> list[ContentTag]:
    metadata = f"{item.name} {item.filename} {item.description}".casefold()
    matches = [
        tag
        for tag, keywords in CONTENT_KEYWORDS.items()
        if any(keyword in metadata for keyword in keywords)
    ]
    return matches or ["general"]


def infer_model_capability(item: ModelItem) -> ModelCapabilityProfile:
    lowered = f"{item.name} {item.filename}".lower()
    content_tags = infer_content_tags(item)
    if item.kind == "checkpoint" and "wan" in lowered:
        return ModelCapabilityProfile(
            capabilities=["image_to_video", "video_to_video"],
            required_inputs={
                "image_to_video": ["reference_image"],
                "video_to_video": ["reference_video"],
            },
            required_components={
                "image_to_video": ["text_encoder", "vae"],
                "video_to_video": ["text_encoder", "vae"],
            },
            workflow_family={
                "image_to_video": "wan_video",
                "video_to_video": "wan_video",
            },
            recommended_params={
                "image_to_video": {"frames": 41, "fps": 16},
                "video_to_video": {"frames": 33, "fps": 16},
            },
            content_tags=content_tags,
            description_zh="Wan 视频生成模型，可根据图片或视频生成新视频。",
            confirmed=True,
        )

    parent_folder = Path(item.path).parent.name.lower() if item.path else ""
    is_standard_checkpoint = item.kind == "checkpoint" and (
        item.source in {"comfyui", "manager"} or parent_folder == "checkpoints"
    )
    if is_standard_checkpoint and item.usage == "image":
        return ModelCapabilityProfile(
            capabilities=["text_to_image", "image_to_image", "text_to_video"],
            required_inputs={"image_to_image": ["reference_image"]},
            required_components={"text_to_video": ["motion_model"]},
            workflow_family={
                "text_to_image": "standard_checkpoint",
                "image_to_image": "standard_checkpoint",
                "text_to_video": "animatediff",
            },
            recommended_params={
                "text_to_image": {"steps": 25, "cfg": 7, "denoise": 1},
                "image_to_image": {"denoise": 0.5},
                "text_to_video": {"frames": 16, "fps": 8},
            },
            content_tags=content_tags,
            description_zh="标准图片检查点，可生成图片；安装运动模型后可生成短视频。",
            confirmed=True,
        )

    return ModelCapabilityProfile(
        content_tags=content_tags,
        description_zh=PENDING_DESCRIPTION,
    )


class CapabilityStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def _key(filename: str) -> str:
        return filename.strip().casefold()

    def _load_all(self) -> dict[str, ModelCapabilityProfile]:
        if not self.path.exists():
            return {}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return {
            key: ModelCapabilityProfile.model_validate(value)
            for key, value in raw.items()
        }

    def load(self, filename: str) -> ModelCapabilityProfile | None:
        return self._load_all().get(self._key(filename))

    def save(self, filename: str, profile: ModelCapabilityProfile) -> None:
        profiles = self._load_all()
        profiles[self._key(filename)] = profile
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {key: value.model_dump(mode="json") for key, value in profiles.items()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def apply_model_capability(
    item: ModelItem, store: CapabilityStore | None = None
) -> ModelItem:
    profile = store.load(item.filename) if store else None
    return item.model_copy(
        update={"capability_profile": profile or infer_model_capability(item)}
    )
