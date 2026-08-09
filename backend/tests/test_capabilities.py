from pathlib import Path

from fastapi.testclient import TestClient

from app.capabilities import CapabilityStore, infer_model_capability
from app.main import create_app
from app.schemas import ModelCapabilityProfile, ModelItem


def model(filename: str, *, usage: str = "image", path: str | None = None) -> ModelItem:
    return ModelItem(
        id=f"local:checkpoint:{filename}",
        name=Path(filename).stem,
        kind="checkpoint",
        usage=usage,
        filename=filename,
        source="local",
        installed=True,
        path=path,
        description="测试模型",
    )


def test_standard_checkpoint_exposes_supported_tasks_and_requirements(tmp_path: Path) -> None:
    item = model(
        "v1-5-pruned-emaonly.safetensors",
        path=str(tmp_path / "models" / "checkpoints" / "v1-5-pruned-emaonly.safetensors"),
    )

    profile = infer_model_capability(item)

    assert profile.confirmed is True
    assert profile.capabilities == [
        "text_to_image",
        "image_to_image",
        "text_to_video",
    ]
    assert profile.required_inputs["image_to_image"] == ["reference_image"]
    assert profile.required_components["text_to_video"] == ["motion_model"]
    assert profile.workflow_family["text_to_image"] == "standard_checkpoint"
    assert profile.recommended_params["image_to_image"] == {"denoise": 0.5}


def test_wan_checkpoint_exposes_only_supported_video_tasks() -> None:
    profile = infer_model_capability(
        model("wan2.2_fun_inpaint_5B_bf16.safetensors", usage="video")
    )

    assert profile.confirmed is True
    assert profile.capabilities == ["image_to_video", "video_to_video"]
    assert profile.required_inputs == {
        "image_to_video": ["reference_image"],
        "video_to_video": ["reference_video"],
    }
    assert profile.workflow_family == {
        "image_to_video": "wan_video",
        "video_to_video": "wan_video",
    }


def test_unknown_video_model_is_pending_confirmation() -> None:
    profile = infer_model_capability(model("ltx-2-dev.safetensors", usage="video"))

    assert profile.confirmed is False
    assert profile.capabilities == []
    assert profile.description_zh == "暂未识别该模型的生成能力，请先确认用途。"


def test_capability_store_persists_user_override(tmp_path: Path) -> None:
    path = tmp_path / "model-capabilities.json"
    profile = ModelCapabilityProfile(
        capabilities=["text_to_video"],
        required_components={"text_to_video": ["motion_model"]},
        workflow_family={"text_to_video": "animatediff"},
        description_zh="用于制作短动画",
        confirmed=True,
    )

    CapabilityStore(path).save("custom.safetensors", profile)

    assert CapabilityStore(path).load("custom.safetensors") == profile


class CatalogClient:
    async def check_status(self) -> bool:
        return True

    async def object_info(self, node_name: str) -> dict:
        payloads = {
            "CheckpointLoaderSimple": {
                "input": {"required": {"ckpt_name": [["remote.safetensors"]]}}
            },
            "LoraLoader": {"input": {"required": {"lora_name": [[]]}}},
            "VAELoader": {"input": {"required": {"vae_name": [[]]}}},
            "ControlNetLoader": {"input": {"required": {"control_net_name": [[]]}}},
        }
        return {node_name: payloads[node_name]}

    async def manager_model_list(self) -> list[dict]:
        return []


def test_capability_override_endpoint_updates_catalog_and_survives_restart(
    tmp_path: Path,
) -> None:
    comfy_root = tmp_path / "ComfyUI"
    checkpoint_dir = comfy_root / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "custom.safetensors").write_text("model", encoding="utf-8")
    data_dir = tmp_path / "data"

    def make_client() -> TestClient:
        return TestClient(
            create_app(data_dir=data_dir, comfy_factory=lambda _: CatalogClient())
        )

    client = make_client()
    client.put(
        "/api/config",
        json={
            "mode": "local",
            "api_url": "http://127.0.0.1:8188",
            "comfyui_path": str(comfy_root),
        },
    )
    response = client.put(
        "/api/models/capabilities",
        json={
            "filename": "custom.safetensors",
            "capabilities": ["image_to_video"],
            "required_inputs": {"image_to_video": ["reference_image"]},
            "workflow_family": {"image_to_video": "custom_workflow"},
            "description_zh": "自定义图生视频模型",
            "confirmed": True,
        },
    )

    assert response.status_code == 200
    catalog = make_client().get("/api/models/catalog").json()
    custom = next(
        item for item in catalog["local_models"] if item["filename"] == "custom.safetensors"
    )
    assert custom["capability_profile"] == {
        "capabilities": ["image_to_video"],
        "required_inputs": {"image_to_video": ["reference_image"]},
        "required_components": {},
        "workflow_family": {"image_to_video": "custom_workflow"},
        "description_zh": "自定义图生视频模型",
        "recommended_params": {},
        "confirmed": True,
    }
