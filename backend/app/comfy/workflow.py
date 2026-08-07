from copy import deepcopy
from pathlib import Path
import json
import secrets
import sys
from typing import Any

from ..schemas import GenerationRequest, LoRAConfig


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


def _apply_loras(
    workflow: dict, loras: list[LoRAConfig], node_start: int = 11
) -> tuple[list, list]:
    """把 LoRA 链接到 checkpoint 之后，返回 (model 引用, clip 引用)。"""
    if not loras:
        return ["1", 0], ["1", 1]
    model_ref: list = ["1", 0]
    clip_ref: list = ["1", 1]
    next_id = node_start
    for lora in loras:
        workflow[str(next_id)] = {
            "class_type": "LoraLoader",
            "inputs": {
                "model": model_ref,
                "clip": clip_ref,
                "lora_name": lora.name,
                "strength_model": lora.model_strength,
                "strength_clip": lora.clip_strength,
            },
        }
        model_ref = [str(next_id), 0]
        clip_ref = [str(next_id), 1]
        next_id += 1
    return model_ref, clip_ref


def _apply_controlnet(
    workflow: dict,
    controlnet: Any,
    node_start: int = 20,
) -> tuple[list, list] | None:
    """插入 ControlNet 条件链，返回 (positive, negative) 引用；未配置时返回 None。"""
    if controlnet is None:
        return None
    loader_id = str(node_start)
    workflow[loader_id] = {
        "class_type": "ControlNetLoader",
        "inputs": {"control_net_name": controlnet.model},
    }
    processor_id = str(node_start + 1)
    processor = controlnet.preprocessor
    if processor == "canny":
        workflow[processor_id] = {
            "class_type": "Canny",
            "inputs": {
                "image": controlnet.image,
                "low_threshold": 100,
                "high_threshold": 200,
            },
        }
    elif processor == "depth":
        workflow[processor_id] = {
            "class_type": "DepthAnythingPreprocessor",
            "inputs": {"image": controlnet.image, "type": "Depth Anything V2 Small"},
        }
    elif processor == "lineart":
        workflow[processor_id] = {
            "class_type": "LineartPreprocessor",
            "inputs": {"image": controlnet.image},
        }
    elif processor == "openpose":
        workflow[processor_id] = {
            "class_type": "OpenposePreprocessor",
            "inputs": {
                "image": controlnet.image,
                "detect_hand": "enable",
                "detect_body": "enable",
                "detect_face": "enable",
            },
        }
    else:
        workflow[processor_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": controlnet.image},
        }
    apply_id = str(node_start + 2)
    workflow[apply_id] = {
        "class_type": "ControlNetApplyAdvanced",
        "inputs": {
            "conditioning": ["2", 0],
            "negative": ["3", 0],
            "control_net": [loader_id, 0],
            "image": [processor_id, 0],
            "strength": controlnet.strength,
            "start_percent": controlnet.start_percent,
            "end_percent": controlnet.end_percent,
        },
    }
    return [apply_id, 0], [apply_id, 1]


def _apply_hires_fix(
    workflow: dict,
    request: GenerationRequest,
    model_ref: list,
    positive_ref: list,
    negative_ref: list,
    node_start: int = 30,
) -> None:
    """第一次采样后用 LatentUpscale 放大并二次精修，VAEDecode 改接第二次输出。"""
    if request.hires is None:
        return
    scale = max(1.0, request.hires.scale)
    base_width = max(64, (int(request.width / scale) // 8) * 8)
    base_height = max(64, (int(request.height / scale) // 8) * 8)
    if not request.reference_image:
        workflow["4"]["inputs"].update(
            width=base_width,
            height=base_height,
        )
    upscale_id = str(node_start)
    workflow[upscale_id] = {
        "class_type": "LatentUpscale",
        "inputs": {
            "samples": ["5", 0],
            "width": request.width,
            "height": request.height,
            "upscale_method": "bicubic",
            "crop": "disabled",
        },
    }
    second_id = str(node_start + 1)
    workflow[second_id] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": secrets.randbelow(2**63),
            "steps": request.hires.steps,
            "cfg": request.cfg,
            "sampler_name": request.sampler,
            "scheduler": request.scheduler,
            "denoise": request.hires.denoise,
            "model": model_ref,
            "positive": positive_ref,
            "negative": negative_ref,
            "latent_image": [upscale_id, 0],
        },
    }
    workflow["6"]["inputs"]["samples"] = [second_id, 0]


def build_text_to_image_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    workflow = json.loads(template_path().read_text(encoding="utf-8"))
    workflow = deepcopy(workflow)
    workflow["1"]["inputs"]["ckpt_name"] = request.checkpoint
    model_ref, clip_ref = _apply_loras(workflow, request.loras)
    workflow["2"]["inputs"]["text"] = request.prompt
    workflow["2"]["inputs"]["clip"] = clip_ref
    workflow["3"]["inputs"]["text"] = request.negative_prompt
    workflow["3"]["inputs"]["clip"] = clip_ref
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
    workflow["5"]["inputs"]["model"] = model_ref
    control_refs = _apply_controlnet(workflow, request.controlnet)
    if control_refs:
        workflow["5"]["inputs"]["positive"] = control_refs[0]
        workflow["5"]["inputs"]["negative"] = control_refs[1]
    positive_ref = control_refs[0] if control_refs else ["2", 0]
    negative_ref = control_refs[1] if control_refs else ["3", 0]
    _apply_hires_fix(workflow, request, model_ref, positive_ref, negative_ref)
    workflow["7"]["inputs"]["filename_prefix"] = output_prefix or request.output_prefix
    if request.reference_image:
        workflow["9"] = {
            "class_type": "LoadImage",
            "inputs": {"image": request.reference_image},
        }
        workflow["10"] = {
            "class_type": "VAEEncode",
            "inputs": {"pixels": ["9", 0], "vae": ["1", 2]},
        }
        workflow["5"]["inputs"]["latent_image"] = ["10", 0]
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
    model_ref, clip_ref = _apply_loras(workflow, request.loras)
    workflow["2"]["inputs"]["text"] = request.prompt
    workflow["2"]["inputs"]["clip"] = clip_ref
    workflow["3"]["inputs"]["text"] = request.negative_prompt
    workflow["3"]["inputs"]["clip"] = clip_ref
    workflow["5"]["inputs"] = {
        "width": request.width,
        "height": request.height,
        "batch_size": request.frames,
    }
    motion_model = request.motion_model or "mm_sd_v15_v2.ckpt"
    workflow["4"]["inputs"]["model_name"] = motion_model
    workflow["4"]["inputs"]["model"] = model_ref
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
        filename_prefix=output_prefix or request.output_prefix,
    )
    if request.vae and request.vae != "pixel_space":
        workflow["9"] = {
            "class_type": "VAELoader",
            "inputs": {"vae_name": request.vae},
        }
        workflow["7"]["inputs"]["vae"] = ["9", 0]
    return workflow
