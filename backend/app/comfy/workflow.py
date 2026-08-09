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
    workflow: dict,
    loras: list[LoRAConfig],
    model_ref: list | None = None,
    clip_ref: list | None = None,
    node_start: int = 11,
) -> tuple[list, list]:
    """把 LoRA 链接到给定 model/clip 之后，返回 (model 引用, clip 引用)。"""
    if not loras:
        return model_ref or ["1", 0], clip_ref or ["1", 1]
    model_ref = model_ref or ["1", 0]
    clip_ref = clip_ref or ["1", 1]
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
    image_loader_id = str(node_start + 1)
    workflow[image_loader_id] = {
        "class_type": "LoadImage",
        "inputs": {"image": controlnet.image},
    }
    processor = controlnet.preprocessor
    image_ref = [image_loader_id, 0]
    if processor == "canny":
        processor_id = str(node_start + 2)
        workflow[processor_id] = {
            "class_type": "Canny",
            "inputs": {
                "image": image_ref,
                "low_threshold": 0.4,
                "high_threshold": 0.8,
            },
        }
        image_ref = [processor_id, 0]
    elif processor == "depth":
        processor_id = str(node_start + 2)
        workflow[processor_id] = {
            "class_type": "DepthAnythingPreprocessor",
            "inputs": {"image": image_ref, "type": "Depth Anything V2 Small"},
        }
        image_ref = [processor_id, 0]
    elif processor == "lineart":
        processor_id = str(node_start + 2)
        workflow[processor_id] = {
            "class_type": "LineartPreprocessor",
            "inputs": {"image": image_ref},
        }
        image_ref = [processor_id, 0]
    elif processor == "openpose":
        processor_id = str(node_start + 2)
        workflow[processor_id] = {
            "class_type": "OpenposePreprocessor",
            "inputs": {
                "image": image_ref,
                "detect_hand": "enable",
                "detect_body": "enable",
                "detect_face": "enable",
            },
        }
        image_ref = [processor_id, 0]
    apply_id = str(node_start + (3 if processor != "none" else 2))
    workflow[apply_id] = {
        "class_type": "ControlNetApplyAdvanced",
        "inputs": {
            "conditioning": ["2", 0],
            "negative": ["3", 0],
            "control_net": [loader_id, 0],
            "image": image_ref,
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
    uses_reference: bool = False,
) -> None:
    """第一次采样后用 LatentUpscale 放大并二次精修，VAEDecode 改接第二次输出。"""
    if request.hires is None:
        return
    scale = max(1.0, request.hires.scale)
    base_width = max(64, (int(request.width / scale) // 8) * 8)
    base_height = max(64, (int(request.height / scale) // 8) * 8)
    if not uses_reference:
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


def _wan_model_chain(
    workflow: dict,
    request: GenerationRequest,
    node_start: int = 1,
) -> tuple[list, list, list]:
    """构建 Wan 三件套（UNETLoader + CLIPLoader + VAELoader），返回 (model, clip, vae) 引用。"""
    unet_id = str(node_start)
    workflow[unet_id] = {
        "class_type": "UNETLoader",
        "inputs": {
            "unet_name": request.checkpoint,
            "weight_dtype": "default",
        },
    }
    clip_id = str(node_start + 1)
    workflow[clip_id] = {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
            "type": "wan",
            "device": "default",
            "dtype": "default",
        },
    }
    vae_id = str(node_start + 2)
    workflow[vae_id] = {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "wan2.2_vae.safetensors"},
    }
    model_ref, clip_ref = _apply_loras(
        workflow, request.loras, [unet_id, 0], [clip_id, 0], node_start=20
    )
    return model_ref, clip_ref, [vae_id, 0]


def build_wan_video_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    """构建 Wan 图生视频 / 视频生视频工作流。"""
    workflow: dict[str, Any] = {}
    model_ref, clip_ref, vae_ref = _wan_model_chain(workflow, request)
    workflow["4"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": request.prompt, "clip": clip_ref},
    }
    workflow["5"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": request.negative_prompt, "clip": clip_ref},
    }
    length = max(2, request.frames)
    if request.video_mode == "i2v":
        workflow["6"] = {
            "class_type": "LoadImage",
            "inputs": {"image": request.reference_image},
        }
        wan_node: dict[str, Any] = {
            "class_type": "WanImageToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": vae_ref,
                "start_image": ["6", 0],
                "width": request.width,
                "height": request.height,
                "length": length,
                "batch_size": 1,
            },
        }
        workflow["9"] = wan_node
    else:
        workflow["6"] = {
            "class_type": "LoadVideo",
            "inputs": {
                "video": request.reference_video,
                "frame_load_cap": length,
                "skip_first_frames": 0,
                "select_every_nth": 1,
            },
        }
        workflow["7"] = {
            "class_type": "ImageFromBatch",
            "inputs": {"image": ["6", 0], "batch_index": 0, "length": 1},
        }
        workflow["8"] = {
            "class_type": "ImageFromBatch",
            "inputs": {"image": ["6", 0], "batch_index": length - 1, "length": 1},
        }
        workflow["9"] = {
            "class_type": "WanVideoToVideo",
            "inputs": {
                "positive": ["4", 0],
                "negative": ["5", 0],
                "vae": vae_ref,
                "start_image": ["7", 0],
                "end_image": ["8", 0],
                "width": request.width,
                "height": request.height,
                "length": length,
                "batch_size": 1,
            },
        }
    workflow["10"] = {
        "class_type": "KSampler",
        "inputs": {
            "seed": request.seed if request.seed >= 0 else secrets.randbelow(2**63),
            "steps": request.steps,
            "cfg": request.cfg,
            "sampler_name": request.sampler,
            "scheduler": request.scheduler,
            "denoise": request.denoise,
            "model": model_ref,
            "positive": ["9", 0],
            "negative": ["9", 1],
            "latent_image": ["9", 2],
        },
    }
    workflow["11"] = {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["10", 0], "vae": vae_ref},
    }
    workflow["12"] = {
        "class_type": "SaveAnimatedWEBP",
        "inputs": {
            "images": ["11", 0],
            "fps": request.fps,
            "lossless": request.lossless,
            "quality": request.quality,
            "method": request.method,
            "filename_prefix": output_prefix or request.output_prefix,
        },
    }
    return workflow


def _build_standard_image_workflow(
    request: GenerationRequest,
    output_prefix: str,
    uses_reference: bool,
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
    _apply_hires_fix(
        workflow,
        request,
        model_ref,
        positive_ref,
        negative_ref,
        uses_reference=uses_reference,
    )
    workflow["7"]["inputs"]["filename_prefix"] = output_prefix or request.output_prefix
    if uses_reference:
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


def build_text_to_image_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    return _build_standard_image_workflow(request, output_prefix, uses_reference=False)


def build_image_to_image_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    if not request.reference_image.strip():
        raise ValueError("图生图需要参考图片")
    return _build_standard_image_workflow(request, output_prefix, uses_reference=True)


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


def build_image_to_video_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    if not request.reference_image.strip():
        raise ValueError("图生视频需要参考图片")
    return build_wan_video_workflow(
        request.model_copy(update={"video_mode": "i2v"}), output_prefix
    )


def build_video_to_video_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    if not request.reference_video.strip():
        raise ValueError("视频生视频需要参考视频")
    return build_wan_video_workflow(
        request.model_copy(update={"video_mode": "v2v"}), output_prefix
    )


def build_workflow(
    request: GenerationRequest, output_prefix: str = "AIArtAgent"
) -> dict:
    builders = {
        "text_to_image": build_text_to_image_workflow,
        "image_to_image": build_image_to_image_workflow,
        "text_to_video": build_text_to_video_workflow,
        "image_to_video": build_image_to_video_workflow,
        "video_to_video": build_video_to_video_workflow,
    }
    return builders[request.creation_type](request, output_prefix)
