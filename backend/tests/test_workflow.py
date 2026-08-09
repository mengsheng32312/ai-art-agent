import json
import sys

from app.comfy.workflow import (
    build_image_to_image_workflow,
    build_image_to_video_workflow,
    build_text_to_image_workflow,
    build_text_to_video_workflow,
    build_video_to_video_workflow,
    build_workflow,
)
from app.schemas import GenerationRequest


def test_build_workflow_replaces_generation_parameters() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        negative_prompt="blurry",
        checkpoint="model.safetensors",
        width=768,
        height=512,
        steps=30,
        cfg=6.5,
        seed=42,
        sampler="dpmpp_2m",
        scheduler="karras",
        batch_size=2,
    )

    workflow = build_text_to_image_workflow(request, output_prefix="AIArtAgent/task-42")

    assert workflow["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert workflow["2"]["inputs"]["text"] == "a red fox"
    assert workflow["3"]["inputs"]["text"] == "blurry"
    assert workflow["4"]["inputs"] == {"width": 768, "height": 512, "batch_size": 2}
    assert workflow["5"]["inputs"]["seed"] == 42
    assert workflow["5"]["inputs"]["steps"] == 30
    assert workflow["5"]["inputs"]["cfg"] == 6.5
    assert workflow["5"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert workflow["5"]["inputs"]["scheduler"] == "karras"
    assert workflow["7"]["inputs"]["filename_prefix"] == "AIArtAgent/task-42"


def test_build_workflow_reads_the_packaged_template(monkeypatch, tmp_path) -> None:
    template = {
        "packaged_fixture": True,
        "1": {"inputs": {"ckpt_name": ""}},
        "2": {"inputs": {"text": ""}},
        "3": {"inputs": {"text": ""}},
        "4": {"inputs": {}},
        "5": {"inputs": {}},
        "7": {"inputs": {"filename_prefix": ""}},
    }
    workflow_dir = tmp_path / "workflows"
    workflow_dir.mkdir()
    (workflow_dir / "text-to-image.json").write_text(
        json.dumps(template), encoding="utf-8"
    )
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    workflow = build_text_to_image_workflow(
        GenerationRequest(prompt="fox", checkpoint="model.safetensors")
    )

    assert workflow["packaged_fixture"] is True


def test_reference_image_uses_load_image_and_vae_encode() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        reference_image="ref.png",
        denoise=0.5,
    )

    workflow = build_image_to_image_workflow(request)

    assert workflow["9"] == {
        "class_type": "LoadImage",
        "inputs": {"image": "ref.png"},
    }
    assert workflow["10"] == {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["9", 0], "vae": ["1", 2]},
    }
    assert workflow["5"]["inputs"]["latent_image"] == ["10", 0]
    assert workflow["5"]["inputs"]["denoise"] == 0.5


def test_workflow_without_reference_image_keeps_empty_latent() -> None:
    request = GenerationRequest(prompt="a red fox", checkpoint="model.safetensors")

    workflow = build_text_to_image_workflow(request)

    assert "9" not in workflow
    assert "10" not in workflow
    assert workflow["5"]["inputs"]["latent_image"] == ["4", 0]


def test_image_workflow_chains_lora_after_checkpoint() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        loras=[
            {"name": "detail.safetensors", "model_strength": 0.8, "clip_strength": 0.6},
            {"name": "style.safetensors", "model_strength": 1.0, "clip_strength": 1.0},
        ],
    )

    workflow = build_text_to_image_workflow(request)

    assert workflow["11"]["class_type"] == "LoraLoader"
    assert workflow["11"]["inputs"] == {
        "model": ["1", 0],
        "clip": ["1", 1],
        "lora_name": "detail.safetensors",
        "strength_model": 0.8,
        "strength_clip": 0.6,
    }
    assert workflow["12"]["inputs"]["model"] == ["11", 0]
    assert workflow["12"]["inputs"]["clip"] == ["11", 1]
    assert workflow["5"]["inputs"]["model"] == ["12", 0]
    assert workflow["2"]["inputs"]["clip"] == ["12", 1]
    assert workflow["3"]["inputs"]["clip"] == ["12", 1]


def test_video_workflow_applies_lora_before_animatediff() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        media_type="video",
        motion_model="mm_sd_v15_v2.ckpt",
        loras=[{"name": "style.safetensors", "model_strength": 0.9, "clip_strength": 0.7}],
    )

    workflow = build_text_to_video_workflow(request)

    assert workflow["11"]["class_type"] == "LoraLoader"
    assert workflow["11"]["inputs"]["lora_name"] == "style.safetensors"
    assert workflow["4"]["inputs"]["model"] == ["11", 0]
    assert workflow["2"]["inputs"]["clip"] == ["11", 1]


def test_workflow_without_loras_keeps_direct_connections() -> None:
    request = GenerationRequest(prompt="a red fox", checkpoint="model.safetensors")

    workflow = build_text_to_image_workflow(request)

    assert "11" not in workflow
    assert workflow["5"]["inputs"]["model"] == ["1", 0]
    assert workflow["2"]["inputs"]["clip"] == ["1", 1]


def test_image_workflow_applies_controlnet_with_canny_preprocessor() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        controlnet={
            "model": "control_v11p_sd15_canny.safetensors",
            "preprocessor": "canny",
            "image": "edge.png",
            "strength": 0.9,
            "start_percent": 0.1,
            "end_percent": 0.8,
        },
    )

    workflow = build_text_to_image_workflow(request)

    assert workflow["20"]["class_type"] == "ControlNetLoader"
    assert workflow["20"]["inputs"]["control_net_name"] == (
        "control_v11p_sd15_canny.safetensors"
    )
    assert workflow["21"]["class_type"] == "Canny"
    assert workflow["21"]["inputs"]["image"] == "edge.png"
    assert workflow["22"]["class_type"] == "ControlNetApplyAdvanced"
    assert workflow["22"]["inputs"] == {
        "conditioning": ["2", 0],
        "negative": ["3", 0],
        "control_net": ["20", 0],
        "image": ["21", 0],
        "strength": 0.9,
        "start_percent": 0.1,
        "end_percent": 0.8,
    }
    assert workflow["5"]["inputs"]["positive"] == ["22", 0]
    assert workflow["5"]["inputs"]["negative"] == ["22", 1]


def test_image_workflow_controlnet_none_preprocessor_uses_raw_image() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        controlnet={
            "model": "control_v11p_sd15_scribble.safetensors",
            "preprocessor": "none",
            "image": "sketch.png",
        },
    )

    workflow = build_text_to_image_workflow(request)

    assert workflow["21"]["class_type"] == "LoadImage"
    assert workflow["21"]["inputs"]["image"] == "sketch.png"
    assert workflow["22"]["inputs"]["image"] == ["21", 0]


def test_workflow_without_controlnet_keeps_direct_conditioning() -> None:
    request = GenerationRequest(prompt="a red fox", checkpoint="model.safetensors")

    workflow = build_text_to_image_workflow(request)

    assert "20" not in workflow
    assert workflow["5"]["inputs"]["positive"] == ["2", 0]
    assert workflow["5"]["inputs"]["negative"] == ["3", 0]


def test_image_workflow_applies_hires_fix_second_sampler() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        width=1024,
        height=1024,
        hires={"scale": 2.0, "steps": 12, "denoise": 0.5},
    )

    workflow = build_text_to_image_workflow(request)

    assert workflow["4"]["inputs"]["width"] == 512
    assert workflow["4"]["inputs"]["height"] == 512
    assert workflow["30"]["class_type"] == "LatentUpscale"
    assert workflow["30"]["inputs"] == {
        "samples": ["5", 0],
        "width": 1024,
        "height": 1024,
        "upscale_method": "bicubic",
        "crop": "disabled",
    }
    assert workflow["31"]["class_type"] == "KSampler"
    assert workflow["31"]["inputs"]["steps"] == 12
    assert workflow["31"]["inputs"]["denoise"] == 0.5
    assert workflow["31"]["inputs"]["latent_image"] == ["30", 0]
    assert workflow["6"]["inputs"]["samples"] == ["31", 0]


def test_hires_fix_respects_reference_image_size() -> None:
    request = GenerationRequest(
        prompt="a red fox",
        checkpoint="model.safetensors",
        reference_image="ref.png",
        width=1024,
        height=1024,
        hires={"scale": 2.0, "steps": 10, "denoise": 0.4},
    )

    workflow = build_image_to_image_workflow(request)

    # 参考图模式下首次采样 latent 来自参考图，EmptyLatentImage 尺寸保持原值。
    assert workflow["4"]["inputs"]["width"] == 1024
    assert workflow["30"]["inputs"]["width"] == 1024
    assert workflow["6"]["inputs"]["samples"] == ["31", 0]


def test_workflow_without_hires_keeps_single_sampler() -> None:
    request = GenerationRequest(prompt="a red fox", checkpoint="model.safetensors")

    workflow = build_text_to_image_workflow(request)

    assert "30" not in workflow
    assert "31" not in workflow
    assert workflow["6"]["inputs"]["samples"] == ["5", 0]


def test_wan_i2v_workflow_builds_image_to_video_chain() -> None:
    request = GenerationRequest(
        prompt="a cat walking",
        checkpoint="wan2.2_i2v_14B_fp8_scaled.safetensors",
        media_type="video",
        video_mode="i2v",
        reference_image="first.png",
        frames=41,
        width=832,
        height=480,
        fps=16,
    )

    workflow = build_image_to_video_workflow(request)

    assert workflow["1"]["class_type"] == "UNETLoader"
    assert workflow["1"]["inputs"]["unet_name"] == (
        "wan2.2_i2v_14B_fp8_scaled.safetensors"
    )
    assert workflow["2"]["class_type"] == "CLIPLoader"
    assert workflow["2"]["inputs"]["type"] == "wan"
    assert workflow["3"]["class_type"] == "VAELoader"
    assert workflow["6"]["class_type"] == "LoadImage"
    assert workflow["6"]["inputs"]["image"] == "first.png"
    assert workflow["9"]["class_type"] == "WanImageToVideo"
    assert workflow["9"]["inputs"]["start_image"] == ["6", 0]
    assert workflow["9"]["inputs"]["length"] == 41
    assert workflow["10"]["inputs"]["model"] == ["1", 0]
    assert workflow["12"]["class_type"] == "SaveAnimatedWEBP"
    assert workflow["12"]["inputs"]["fps"] == 16


def test_wan_v2v_workflow_extracts_first_and_last_frames() -> None:
    request = GenerationRequest(
        prompt="a cat walking",
        checkpoint="wan2.2_v2v_14B_fp8_scaled.safetensors",
        media_type="video",
        video_mode="v2v",
        reference_video="clip.mp4",
        frames=33,
    )

    workflow = build_video_to_video_workflow(request)

    assert workflow["6"]["class_type"] == "LoadVideo"
    assert workflow["6"]["inputs"]["video"] == "clip.mp4"
    assert workflow["6"]["inputs"]["frame_load_cap"] == 33
    assert workflow["7"]["class_type"] == "ImageFromBatch"
    assert workflow["7"]["inputs"]["batch_index"] == 0
    assert workflow["8"]["class_type"] == "ImageFromBatch"
    assert workflow["8"]["inputs"]["batch_index"] == 32
    assert workflow["9"]["class_type"] == "WanVideoToVideo"
    assert workflow["9"]["inputs"]["start_image"] == ["7", 0]
    assert workflow["9"]["inputs"]["end_image"] == ["8", 0]


def test_wan_workflow_applies_loras_to_model_and_clip() -> None:
    request = GenerationRequest(
        prompt="a cat walking",
        checkpoint="wan2.2_i2v_14B_fp8_scaled.safetensors",
        media_type="video",
        video_mode="i2v",
        reference_image="first.png",
        loras=[{"name": "style.safetensors", "model_strength": 0.9, "clip_strength": 0.7}],
    )

    workflow = build_image_to_video_workflow(request)

    assert workflow["20"]["class_type"] == "LoraLoader"
    assert workflow["20"]["inputs"]["model"] == ["1", 0]
    assert workflow["20"]["inputs"]["clip"] == ["2", 0]
    assert workflow["10"]["inputs"]["model"] == ["20", 0]
    assert workflow["4"]["inputs"]["clip"] == ["20", 1]


def test_animate_diff_t2v_workflow_unchanged_by_default() -> None:
    request = GenerationRequest(
        prompt="a cat walking",
        checkpoint="model.safetensors",
        media_type="video",
        motion_model="mm_sd_v15_v2.ckpt",
    )

    workflow = build_text_to_video_workflow(request)

    assert workflow["4"]["class_type"] == "ADE_AnimateDiffLoaderGen1"
    assert "WanImageToVideo" not in str(workflow)


def test_explicit_text_to_image_does_not_infer_image_to_image_from_stale_reference() -> None:
    request = GenerationRequest(
        prompt="a cat",
        checkpoint="model.safetensors",
        creation_type="text_to_image",
        reference_image="stale.png",
    )

    workflow = build_workflow(request)

    assert "LoadImage" not in {node["class_type"] for node in workflow.values()}
    assert workflow["5"]["inputs"]["latent_image"] == ["4", 0]


def test_build_workflow_routes_all_explicit_creation_types() -> None:
    requests = {
        "text_to_image": GenerationRequest(
            prompt="cat", checkpoint="image.safetensors", creation_type="text_to_image"
        ),
        "image_to_image": GenerationRequest(
            prompt="cat",
            checkpoint="image.safetensors",
            creation_type="image_to_image",
            reference_image="ref.png",
        ),
        "text_to_video": GenerationRequest(
            prompt="cat",
            checkpoint="image.safetensors",
            creation_type="text_to_video",
            motion_model="mm.ckpt",
        ),
        "image_to_video": GenerationRequest(
            prompt="cat",
            checkpoint="wan.safetensors",
            creation_type="image_to_video",
            reference_image="ref.png",
        ),
        "video_to_video": GenerationRequest(
            prompt="cat",
            checkpoint="wan.safetensors",
            creation_type="video_to_video",
            reference_video="ref.mp4",
        ),
    }

    workflows = {name: build_workflow(request) for name, request in requests.items()}

    assert workflows["text_to_image"]["4"]["class_type"] == "EmptyLatentImage"
    assert workflows["image_to_image"]["9"]["class_type"] == "LoadImage"
    assert workflows["text_to_video"]["4"]["class_type"] == "ADE_AnimateDiffLoaderGen1"
    assert workflows["image_to_video"]["9"]["class_type"] == "WanImageToVideo"
    assert workflows["video_to_video"]["9"]["class_type"] == "WanVideoToVideo"


def test_reference_based_workflows_reject_missing_required_media() -> None:
    missing_image = GenerationRequest(
        prompt="cat", checkpoint="image.safetensors", creation_type="image_to_image"
    )
    missing_video = GenerationRequest(
        prompt="cat", checkpoint="wan.safetensors", creation_type="video_to_video"
    )

    try:
        build_workflow(missing_image)
        raise AssertionError("图生图缺少参考图时必须失败")
    except ValueError as exc:
        assert str(exc) == "图生图需要参考图片"

    try:
        build_workflow(missing_video)
        raise AssertionError("视频生视频缺少参考视频时必须失败")
    except ValueError as exc:
        assert str(exc) == "视频生视频需要参考视频"
