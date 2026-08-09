from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class FakeModelComfyClient:
    def __init__(self) -> None:
        self.install_calls: list[dict] = []

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
                "base": "SD1.5",
                "save_path": "checkpoints",
                "url": "https://example.com/downloadable.safetensors",
            },
        ]

    async def manager_install_model(self, model: dict) -> None:
        self.install_calls.append(model)

    async def manager_queue_status(self) -> dict:
        return {
            "total_count": 1,
            "done_count": 0,
            "in_progress_count": 1,
            "is_processing": True,
        }

    async def upload_media(self, kind: str, data: bytes, filename: str) -> str:
        self.upload_calls = getattr(self, "upload_calls", [])
        self.upload_calls.append((kind, filename))
        return f"remote-{filename}"


class UnetModelComfyClient(FakeModelComfyClient):
    async def object_info(self, node_name: str) -> dict:
        if node_name == "UNETLoader":
            return {
                "UNETLoader": {
                    "input": {
                        "required": {
                            "unet_name": [["wan2.2_i2v_14B_fp8_scaled.safetensors"]]
                        }
                    }
                }
            }
        return await super().object_info(node_name)


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


def test_model_catalog_scans_the_selected_local_model_directory(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    model_root = tmp_path / "shared-models"
    checkpoint_dir = model_root / "checkpoints"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "local-only.safetensors").write_text("model", encoding="utf-8")

    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: FakeModelComfyClient())
    )
    client.put(
        "/api/config",
        json={
            "mode": "local",
            "api_url": "http://127.0.0.1:8188",
            "comfyui_path": str(comfy_root),
            "local_model_path": str(model_root),
        },
    )

    catalog = client.get("/api/models/catalog").json()

    assert [item["filename"] for item in catalog["local_models"]] == [
        "local-only.safetensors"
    ]


def test_model_catalog_includes_diffusion_models_exposed_by_unet_loader(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(
            data_dir=tmp_path / "data",
            comfy_factory=lambda _: UnetModelComfyClient(),
        )
    )

    catalog = client.get("/api/models/catalog").json()

    wan = next(
        item
        for item in catalog["remote_models"]
        if item["filename"] == "wan2.2_i2v_14B_fp8_scaled.safetensors"
    )
    assert wan["capability_profile"]["capabilities"] == [
        "image_to_video",
        "video_to_video",
    ]


def test_model_catalog_resolves_a_windows_portable_outer_directory(tmp_path: Path) -> None:
    portable_root = tmp_path / "ComfyUI_windows_portable"
    model_root = portable_root / "ComfyUI" / "models"
    (model_root / "checkpoints").mkdir(parents=True)
    (model_root / "diffusion_models").mkdir()
    (model_root / "text_encoders").mkdir()
    (model_root / "checkpoints" / "image.safetensors").write_text("model")
    (model_root / "diffusion_models" / "video.safetensors").write_text("model")
    (model_root / "text_encoders" / "encoder.safetensors").write_text("model")

    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: FakeModelComfyClient())
    )
    client.put(
        "/api/config",
        json={
            "mode": "local",
            "api_url": "http://127.0.0.1:8188",
            "comfyui_path": str(portable_root),
        },
    )

    catalog = client.get("/api/models/catalog").json()

    assert {
        (item["filename"], item["kind"])
        for item in catalog["local_models"]
    } == {
        ("image.safetensors", "checkpoint"),
        ("video.safetensors", "checkpoint"),
        ("encoder.safetensors", "other"),
    }


def test_download_to_remote_passes_model_metadata_directly(tmp_path: Path) -> None:
    fake = FakeModelComfyClient()
    client = TestClient(
        create_app(
            data_dir=tmp_path / "data", comfy_factory=lambda _: fake
        )
    )
    client.put(
        "/api/config",
        json={
            "mode": "remote",
            "api_url": "http://comfy",
        },
    )

    catalog = client.get("/api/models/catalog").json()
    downloadable = next(
        item
        for item in catalog["online_models"]
        if item["filename"] == "downloadable.safetensors"
    )
    response = client.post(
        "/api/models/download",
        json={"model_id": downloadable["id"], "destination": "remote"},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "downloadable.safetensors"
    assert fake.install_calls == [
        {
            "name": "Downloadable",
            "filename": "downloadable.safetensors",
            "type": "checkpoint",
            "base": "SD1.5",
            "save_path": "checkpoints",
            "url": "https://example.com/downloadable.safetensors",
        }
    ]


def test_manager_queue_status_endpoint(tmp_path: Path) -> None:
    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: FakeModelComfyClient())
    )
    client.put(
        "/api/config",
        json={
            "mode": "remote",
            "api_url": "http://comfy",
        },
    )

    response = client.get("/api/models/manager/status")

    assert response.status_code == 200
    assert response.json() == {
        "total_count": 1,
        "done_count": 0,
        "in_progress_count": 1,
        "is_processing": True,
    }


def test_upload_remote_forwards_to_comfy(tmp_path: Path) -> None:
    fake = FakeModelComfyClient()
    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: fake)
    )
    client.put(
        "/api/config",
        json={"mode": "remote", "api_url": "http://comfy"},
    )

    response = client.post(
        "/api/upload",
        params={"kind": "image"},
        files={"file": ("ref.png", b"png-data", "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "remote-ref.png",
        "path": None,
        "mode": "remote",
    }
    assert fake.upload_calls == [("image", "ref.png")]


def test_upload_local_writes_to_input_dir(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    client = TestClient(
        create_app(data_dir=tmp_path / "data", comfy_factory=lambda _: FakeModelComfyClient())
    )
    client.put(
        "/api/config",
        json={
            "mode": "local",
            "api_url": "http://127.0.0.1:8188",
            "comfyui_path": str(comfy_root),
        },
    )

    response = client.post(
        "/api/upload",
        params={"kind": "video"},
        files={"file": ("clip.mp4", b"mp4-data", "video/mp4")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "name": "clip.mp4",
        "path": str(comfy_root / "input" / "clip.mp4"),
        "mode": "local",
    }
    assert (comfy_root / "input" / "clip.mp4").read_bytes() == b"mp4-data"
