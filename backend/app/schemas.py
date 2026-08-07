from typing import Literal

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    prompt: str = Field(min_length=1)
    negative_prompt: str = ""
    checkpoint: str = Field(min_length=1)
    media_type: Literal["image", "video"] = "image"
    vae: str | None = None
    frames: int = Field(default=16, ge=2, le=120)
    motion_model: str | None = None
    beta_schedule: str = "sqrt_linear (AnimateDiff)"
    fps: int = Field(default=8, ge=1, le=60)
    quality: int = Field(default=80, ge=1, le=100)
    lossless: bool = False
    method: str = "default"
    output_prefix: str = "AIArtAgent"
    width: int = Field(default=1024, ge=64, le=4096, multiple_of=8)
    height: int = Field(default=1024, ge=64, le=4096, multiple_of=8)
    steps: int = Field(default=25, ge=1, le=150)
    cfg: float = Field(default=7, ge=0, le=30)
    denoise: float = Field(default=1, ge=0, le=1)
    seed: int = Field(default=-1, ge=-1)
    sampler: str = "euler"
    scheduler: str = "normal"
    batch_size: int = Field(default=1, ge=1, le=8)


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
