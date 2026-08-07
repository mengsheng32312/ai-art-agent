import json
import sys

from app.comfy.workflow import build_text_to_image_workflow
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
