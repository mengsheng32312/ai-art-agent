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


class StatefulComfyClient(FakeComfyClient):
    def __init__(self, history_payload: dict | None, queue_payload: dict | None = None) -> None:
        self.history_payload = history_payload
        self.queue_payload = queue_payload or {
            "queue_running": [],
            "queue_pending": [],
        }

    async def history(self, prompt_id: str) -> dict:
        if self.history_payload is None:
            return {}
        return {prompt_id: self.history_payload}

    async def queue(self) -> dict:
        return self.queue_payload


def submit_generation(client: TestClient) -> str:
    response = client.post(
        "/api/generations",
        json={"prompt": "fox", "checkpoint": "model.safetensors"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_generation_is_queued_and_saved(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))
    client.put("/api/config", json={"mode": "remote", "api_url": "http://comfy/"})

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
    assert completed["outputs"][0] == (
        "http://comfy/view?filename=fox.png&subfolder=&type=output"
    )


def test_generation_becomes_running_when_comfy_has_started(tmp_path) -> None:
    comfy = StatefulComfyClient(
        {
            "outputs": {},
            "status": {"completed": False, "status_str": "success", "messages": []},
        }
    )
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))

    task_id = submit_generation(client)

    running = client.get(f"/api/generations/{task_id}").json()
    assert running["status"] == "running"
    assert running["progress"] == 1
    assert client.get("/api/history").json()[0]["status"] == "running"


def test_generation_uses_the_live_comfy_queue_for_running_state(tmp_path) -> None:
    comfy = StatefulComfyClient(
        None,
        queue_payload={
            "queue_running": [[7, "prompt-1", {}, {}, []]],
            "queue_pending": [],
        },
    )
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))

    task_id = submit_generation(client)

    running = client.get(f"/api/generations/{task_id}").json()
    assert running["status"] == "running"
    assert running["progress"] == 1


def test_generation_records_comfy_execution_error(tmp_path) -> None:
    comfy = StatefulComfyClient(
        {
            "outputs": {},
            "status": {
                "completed": False,
                "status_str": "error",
                "messages": [
                    [
                        "execution_error",
                        {
                            "node_id": "5",
                            "node_type": "KSampler",
                            "exception_message": "CUDA out of memory",
                        },
                    ]
                ],
            },
        }
    )
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))

    task_id = submit_generation(client)

    failed = client.get(f"/api/generations/{task_id}").json()
    assert failed["status"] == "failed"
    assert failed["error"] == "CUDA out of memory"
    assert client.get("/api/history").json()[0]["status"] == "failed"


def test_connection_and_checkpoint_endpoints(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))

    assert client.get("/api/comfy/status").json()["connected"] is True
    assert client.get("/api/comfy/checkpoints").json() == ["model.safetensors"]
