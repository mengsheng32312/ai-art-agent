from fastapi.testclient import TestClient

from app.main import create_app


class FakeComfyClient:
    def __init__(self) -> None:
        self.queued_workflow: dict | None = None

    async def check_status(self) -> bool:
        return True

    async def list_checkpoints(self) -> list[str]:
        return ["model.safetensors"]

    async def queue_prompt(self, workflow, client_id: str) -> str:
        self.queued_workflow = workflow
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


def test_generation_routes_using_creation_type_instead_of_legacy_media_fields(
    tmp_path,
) -> None:
    comfy = FakeComfyClient()
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))

    response = client.post(
        "/api/generations",
        json={
            "prompt": "fox",
            "checkpoint": "model.safetensors",
            "creation_type": "image_to_image",
            "media_type": "video",
            "video_mode": "v2v",
            "reference_image": "ref.png",
        },
    )

    assert response.status_code == 201
    assert response.json()["request"]["creation_type"] == "image_to_image"
    assert comfy.queued_workflow is not None
    assert comfy.queued_workflow["9"]["class_type"] == "LoadImage"


def test_generation_rejects_model_without_confirmed_capability(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))

    response = client.post(
        "/api/generations",
        json={
            "prompt": "fox",
            "checkpoint": "ltx-2-dev.safetensors",
            "creation_type": "text_to_video",
            "motion_model": "mm.ckpt",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "暂未确认该模型的生成能力，请先在模型管理中设置用途。"
    }


def test_generation_rejects_missing_required_component(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: FakeComfyClient()))

    response = client.post(
        "/api/generations",
        json={
            "prompt": "fox",
            "checkpoint": "model.safetensors",
            "creation_type": "text_to_video",
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "文生视频缺少必需组件：运动模型"}


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


def test_candidate_connection_uses_unsaved_config_without_persisting_it(
    tmp_path,
) -> None:
    seen_urls: list[str] = []

    def factory(url: str) -> FakeComfyClient:
        seen_urls.append(url)
        return FakeComfyClient()

    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=factory))
    candidate = {
        "mode": "remote",
        "comfyui_path": None,
        "api_url": "http://candidate-comfy:8188",
    }

    response = client.post("/api/comfy/status", json=candidate)

    assert response.status_code == 200
    assert response.json() == {"connected": True, "message": "ComfyUI 已连接"}
    assert seen_urls == ["http://candidate-comfy:8188"]
    assert client.get("/api/config").json()["api_url"] == "http://127.0.0.1:8188"


def test_candidate_connection_returns_a_disconnected_status(tmp_path) -> None:
    class UnavailableComfyClient(FakeComfyClient):
        async def check_status(self) -> bool:
            raise RuntimeError("candidate unavailable")

    client = TestClient(
        create_app(data_dir=tmp_path, comfy_factory=lambda _: UnavailableComfyClient())
    )

    response = client.post(
        "/api/comfy/status",
        json={
            "mode": "remote",
            "comfyui_path": None,
            "api_url": "http://candidate-comfy:8188",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "connected": False,
        "message": "candidate unavailable",
    }


def test_generation_fails_after_three_confirmed_missing_polls(tmp_path) -> None:
    comfy = StatefulComfyClient(None)
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))
    task_id = submit_generation(client)

    first = client.get(f"/api/generations/{task_id}")
    second = client.get(f"/api/generations/{task_id}")
    third = client.get(f"/api/generations/{task_id}")

    assert first.status_code == 200
    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "queued"
    assert third.json()["status"] == "failed"
    assert "取消或中断" in third.json()["error"]


def test_generation_stays_queued_while_pending_in_comfyui(tmp_path) -> None:
    comfy = StatefulComfyClient(
        None,
        queue_payload={
            "queue_running": [],
            "queue_pending": [[7, "prompt-1", {}, {}, []]],
        },
    )
    client = TestClient(create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy))
    task_id = submit_generation(client)

    response = client.get(f"/api/generations/{task_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["progress"] == 0


def test_gateway_failure_does_not_consume_a_missing_poll(tmp_path) -> None:
    class GatewayThenMissingComfyClient(StatefulComfyClient):
        def __init__(self) -> None:
            super().__init__(None)
            self.history_calls = 0

        async def history(self, prompt_id: str) -> dict:
            self.history_calls += 1
            if self.history_calls == 1:
                raise RuntimeError("gateway unavailable")
            return {}

    comfy = GatewayThenMissingComfyClient()
    client = TestClient(
        create_app(data_dir=tmp_path, comfy_factory=lambda _: comfy),
        raise_server_exceptions=False,
    )
    task_id = submit_generation(client)

    gateway = client.get(f"/api/generations/{task_id}")
    first_missing = client.get(f"/api/generations/{task_id}")
    second_missing = client.get(f"/api/generations/{task_id}")
    third_missing = client.get(f"/api/generations/{task_id}")

    assert gateway.status_code == 502
    assert gateway.json() == {"detail": "暂时无法读取 ComfyUI 任务状态"}
    assert first_missing.json()["status"] == "queued"
    assert second_missing.json()["status"] == "queued"
    assert third_missing.json()["status"] == "failed"
