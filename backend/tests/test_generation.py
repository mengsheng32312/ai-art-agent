from fastapi.testclient import TestClient

from app.main import create_app


class FakeComfyClient:
    async def check_status(self) -> bool:
        return True

    async def list_checkpoints(self) -> list[str]:
        return ["model.safetensors"]

    async def queue_prompt(self, workflow, client_id: str) -> str:
        return "prompt-1"

    async def history(self, prompt_id: str) -> dict:
        return {
            prompt_id: {
                "outputs": {
                    "7": {
                        "images": [
                            {"filename": "fox.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
                "status": {"completed": True},
            }
        }


def test_generation_is_queued_and_saved(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))
    client.put("/api/config", json={"mode": "remote", "api_url": "http://comfy"})

    response = client.post(
        "/api/generations",
        json={"prompt": "fox", "checkpoint": "model.safetensors"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "queued"
    assert response.json()["prompt_id"] == "prompt-1"
    assert client.get("/api/history").json()[0]["id"] == response.json()["id"]
    completed = client.get(f"/api/generations/{response.json()['id']}").json()
    assert completed["status"] == "completed"
    assert completed["outputs"][0].endswith("filename=fox.png&subfolder=&type=output")


def test_connection_and_checkpoint_endpoints(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))

    assert client.get("/api/comfy/status").json()["connected"] is True
    assert client.get("/api/comfy/checkpoints").json() == ["model.safetensors"]
