import json
import sys

from app.comfy.workflow import (
    build_text_to_image_workflow,
    build_text_to_video_workflow,
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

    workflow = build_text_to_image_workflow(request)

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
