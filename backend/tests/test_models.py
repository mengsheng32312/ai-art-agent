from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class FakeModelComfyClient:
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
        return [
            {
                "name": "Remote",
                "filename": "remote.safetensors",
                "type": "checkpoint",
            },
            {
                "name": "Downloadable",
                "filename": "downloadable.safetensors",
                "type": "checkpoint",
            },
        ]


def test_model_catalog_separates_remote_and_local_models(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    checkpoint_dir = comfy_root / "models" / "checkpoints"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "local-only.safetensors").write_text("model", encoding="utf-8")

    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: FakeModelComfyClient())
    )
    client.put(
        "/api/config",
        json={
            "mode": "remote",
            "api_url": "http://comfy",
            "comfyui_path": str(comfy_root),
        },
    )

    catalog = client.get("/api/models/catalog").json()

    assert [item["filename"] for item in catalog["remote_models"]] == [
        "remote.safetensors"
    ]
    assert [item["filename"] for item in catalog["local_models"]] == [
        "local-only.safetensors"
    ]
    online = {item["filename"]: item for item in catalog["online_models"]}
    assert online["remote.safetensors"]["installed"] is True
    assert online["downloadable.safetensors"]["installed"] is False
