from copy import deepcopy
from pathlib import Path
import json
import secrets
import sys

from ..schemas import GenerationRequest


TEMPLATE_PATH = Path(__file__).parents[3] / "workflows" / "text-to-image.json"
VIDEO_TEMPLATE_PATH = Path(__file__).parents[3] / "workflows" / "text-to-video.json"


def template_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "workflows" / "text-to-image.json"
    return TEMPLATE_PATH


def video_template_path() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "workflows" / "text-to-video.json"
    return VIDEO_TEMPLATE_PATH


def build_text_to_image_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    workflow = json.loads(template_path().read_text(encoding="utf-8"))
    workflow = deepcopy(workflow)
    workflow["1"]["inputs"]["ckpt_name"] = request.checkpoint
    workflow["2"]["inputs"]["text"] = request.prompt
    workflow["3"]["inputs"]["text"] = request.negative_prompt
    workflow["4"]["inputs"] = {
        "width": request.width,
        "height": request.height,
        "batch_size": request.batch_size,
    }
    sampler = workflow["5"]["inputs"]
    sampler.update(
        seed=request.seed if request.seed >= 0 else secrets.randbelow(2**63),
        steps=request.steps,
        cfg=request.cfg,
        denoise=request.denoise,
        sampler_name=request.sampler,
        scheduler=request.scheduler,
    )
    workflow["7"]["inputs"]["filename_prefix"] = request.output_prefix or output_prefix
    if request.vae and request.vae != "pixel_space":
        workflow["8"] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": request.vae},
        }
        workflow["6"]["inputs"]["vae"] = ["8", 0]
    return workflow


def build_text_to_video_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    workflow = json.loads(video_template_path().read_text(encoding="utf-8"))
    workflow = deepcopy(workflow)
    workflow["1"]["inputs"]["ckpt_name"] = request.checkpoint
    workflow["2"]["inputs"]["text"] = request.prompt
    workflow["3"]["inputs"]["text"] = request.negative_prompt
    workflow["5"]["inputs"] = {
        "width": request.width,
        "height": request.height,
        "batch_size": request.frames,
    }
    motion_model = request.motion_model or "mm_sd_v15_v2.ckpt"
    workflow["4"]["inputs"]["model_name"] = motion_model
    workflow["4"]["inputs"]["beta_schedule"] = request.beta_schedule
    sampler = workflow["6"]["inputs"]
    sampler.update(
        seed=request.seed if request.seed >= 0 else secrets.randbelow(2**63),
        steps=request.steps,
        cfg=request.cfg,
        denoise=request.denoise,
        sampler_name=request.sampler,
        scheduler=request.scheduler,
    )
    workflow["8"]["inputs"].update(
        fps=request.fps,
        quality=request.quality,
        lossless=request.lossless,
        method=request.method,
        filename_prefix=request.output_prefix or output_prefix,
    )
    if request.vae and request.vae != "pixel_space":
        workflow["9"] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": request.vae},
        }
        workflow["7"]["inputs"]["vae"] = ["9", 0]
    return workflow
