from typing import Literal

from pydantic import BaseModel, Field, model_validator


CreationType = Literal[
    "text_to_image",
    "image_to_image",
    "text_to_video",
    "image_to_video",
    "video_to_video",
]
RequiredInput = Literal["reference_image", "reference_video"]


class LoRAConfig(BaseModel):
    name: str = Field(min_length=1)
    model_strength: float = Field(default=1.0, ge=0, le=4)
    clip_strength: float = Field(default=1.0, ge=0, le=4)


class ControlNetConfig(BaseModel):
    model: str = Field(min_length=1)
    preprocessor: Literal["canny", "depth", "lineart", "openpose", "none"] = "canny"
    image: str = Field(min_length=1)
    strength: float = Field(default=1.0, ge=0, le=4)
    start_percent: float = Field(default=0.0, ge=0, le=1)
    end_percent: float = Field(default=1.0, ge=0, le=1)


class HiresConfig(BaseModel):
    scale: float = Field(default=2.0, ge=1, le=4)
    steps: int = Field(default=12, ge=1, le=60)
    denoise: float = Field(default=0.5, ge=0, le=1)


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    checkpoint: str = Field(min_length=1)
    creation_type: CreationType = "text_to_image"
    media_type: Literal["image", "video"] = "image"
    video_mode: Literal["t2v", "i2v", "v2v"] = "t2v"
    vae: str | None = None
    reference_image: str = ""
    reference_video: str = ""
    frames: int = Field(default=16, ge=2, le=120)
    motion_model: str | None = None
    beta_schedule: str = "sqrt_linear (AnimateDiff)"
    fps: int = Field(default=8, ge=1, le=60)
    quality: int = Field(default=80, ge=1, le=100)
    lossless: bool = False
    method: str = "default"
    output_prefix: str = "AIArtAgent"
    loras: list[LoRAConfig] = []
    controlnet: ControlNetConfig | None = None
    hires: HiresConfig | None = None
    width: int = Field(default=1024, ge=64, le=4096, multiple_of=8)
    height: int = Field(default=1024, ge=64, le=4096, multiple_of=8)
    steps: int = Field(default=25, ge=1, le=150)
    cfg: float = Field(default=7, ge=0, le=30)
    denoise: float = Field(default=1, ge=0, le=1)
    seed: int = Field(default=-1, ge=-1)
    sampler: str = "euler"
    scheduler: str = "normal"
    batch_size: int = Field(default=1, ge=1, le=8)

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_creation_fields(cls, value):
        if not isinstance(value, dict) or value.get("creation_type"):
            return value
        data = dict(value)
        if data.get("media_type") == "video":
            data["creation_type"] = {
                "t2v": "text_to_video",
                "i2v": "image_to_video",
                "v2v": "video_to_video",
            }.get(data.get("video_mode", "t2v"), "text_to_video")
        return data


class ConnectionStatus(BaseModel):
    connected: bool
    message: str


class GenerationTask(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = Field(default=0, ge=0, le=100)
    request: GenerationRequest
    prompt_id: str | None = None
    outputs: list[str] = []
    error: str | None = None


ModelKind = Literal["checkpoint", "lora", "controlnet", "vae", "other"]


class ModelCapabilityProfile(BaseModel):
    capabilities: list[CreationType] = Field(default_factory=list)
    required_inputs: dict[CreationType, list[RequiredInput]] = Field(
        default_factory=dict
    )
    required_components: dict[CreationType, list[str]] = Field(default_factory=dict)
    workflow_family: dict[CreationType, str] = Field(default_factory=dict)
    description_zh: str = ""
    recommended_params: dict[CreationType, dict[str, str | int | float | bool]] = (
        Field(default_factory=dict)
    )
    confirmed: bool = False


class ModelCapabilityUpdate(ModelCapabilityProfile):
    filename: str = Field(min_length=1)


class ModelItem(BaseModel):
    id: str
    name: str
    kind: ModelKind
    usage: Literal["image", "video"] = "image"
    filename: str
    source: Literal["comfyui", "local", "manager"]
    installed: bool
    path: str | None = None
    description: str
    preview_url: str | None = None
    size_label: str | None = None
    reference_url: str | None = None
    capability_profile: ModelCapabilityProfile = Field(
        default_factory=ModelCapabilityProfile
    )


class ModelCatalogResponse(BaseModel):
    connected: bool
    manager_available: bool
    message: str
    remote_models: list[ModelItem] = []
    local_models: list[ModelItem] = []
    online_models: list[ModelItem] = []


class ModelDownloadRequest(BaseModel):
    model_id: str = Field(min_length=1)
    destination: Literal["remote", "local"] = "local"


class ManagerQueueStatus(BaseModel):
    total_count: int
    done_count: int
    in_progress_count: int
    is_processing: bool


class UploadResponse(BaseModel):
    name: str
    path: str | None = None
    mode: Literal["local", "remote"]
