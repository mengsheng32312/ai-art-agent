import httpx
import pytest
import json

from app.comfy.client import ComfyClient


@pytest.mark.asyncio
async def test_client_reads_status_checkpoints_and_queues_prompt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/system_stats":
            return httpx.Response(200, json={"system": {"os": "nt"}})
        if request.url.path == "/object_info/CheckpointLoaderSimple":
            return httpx.Response(
                200,
                json={
                    "CheckpointLoaderSimple": {
                        "input": {"required": {"ckpt_name": [["a.safetensors"]]}}
                    }
                },
            )
        if request.url.path == "/queue":
            return httpx.Response(
                200,
                json={
                    "queue_running": [[7, "prompt-1", {}, {}, []]],
                    "queue_pending": [],
                },
            )
        return httpx.Response(200, json={"prompt_id": "prompt-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        assert await client.check_status() is True
        assert await client.list_checkpoints() == ["a.safetensors"]
        assert await client.queue_prompt({"1": {}}, "client-1") == "prompt-1"
        assert (await client.queue())["queue_running"][0][1] == "prompt-1"


@pytest.mark.asyncio
async def test_manager_version_uses_the_v4_status_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/manager/version":
            return httpx.Response(200, text="V4.1")
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        version = await client.manager_version()

    assert version == "V4.1"


@pytest.mark.asyncio
async def test_manager_install_model_sends_model_metadata_directly() -> None:
    sent: list[dict] = []
    started = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal started
        if request.url.path == "/manager/queue/install_model":
            assert request.headers["content-type"].startswith("application/json")
            sent.append(json.loads(request.read().decode()))
            return httpx.Response(200)
        if request.url.path == "/manager/queue/start":
            started += 1
            return httpx.Response(200)
        return httpx.Response(404)

    model = {
        "name": "Demo",
        "type": "checkpoint",
        "base": "SD1.5",
        "save_path": "checkpoints",
        "url": "https://example.com/demo.safetensors",
        "filename": "demo.safetensors",
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        await client.manager_install_model(model)

    assert sent == [model]
    assert started == 1


@pytest.mark.asyncio
async def test_manager_queue_status_returns_counts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/manager/queue/status":
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "done_count": 1,
                    "in_progress_count": 1,
                    "is_processing": True,
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        status = await client.manager_queue_status()

    assert status == {
        "total_count": 2,
        "done_count": 1,
        "in_progress_count": 1,
        "is_processing": True,
    }


@pytest.mark.asyncio
async def test_upload_media_forwards_to_remote_input() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            assert request.method == "POST"
            body = request.read()
            assert b"ref.png" in body
            return httpx.Response(
                200, json={"name": "ref.png", "subfolder": "", "type": "input"}
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        name = await client.upload_media("image", b"png-data", "ref.png")

    assert name == "ref.png"


@pytest.mark.asyncio
async def test_upload_media_uses_video_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/video":
            assert b"clip.mp4" in request.read()
            return httpx.Response(200, json={"name": "clip.mp4"})
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        name = await client.upload_media("video", b"mp4-data", "clip.mp4")

    assert name == "clip.mp4"


@pytest.mark.asyncio
async def test_list_loras_returns_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/object_info/LoraLoader":
            return httpx.Response(
                200,
                json={
                    "LoraLoader": {
                        "input": {"required": {"lora_name": [["a.safetensors", "b.safetensors"]]}}
                    }
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        names = await client.list_loras()

    assert names == ["a.safetensors", "b.safetensors"]


@pytest.mark.asyncio
async def test_list_controlnets_returns_names() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/object_info/ControlNetLoader":
            return httpx.Response(
                200,
                json={
                    "ControlNetLoader": {
                        "input": {
                            "required": {"control_net_name": [["cn.safetensors"]]}
                        }
                    }
                },
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        names = await client.list_controlnets()

    assert names == ["cn.safetensors"]


@pytest.mark.asyncio
async def test_queue_prompt_reports_comfy_validation_details() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "type": "prompt_outputs_failed_validation",
                    "message": "Prompt outputs failed validation",
                },
                "node_errors": {
                    "20": {
                        "class_type": "ControlNetLoader",
                        "errors": [
                            {
                                "type": "value_not_in_list",
                                "message": "Value not in list",
                                "details": "control_net_name: 'missing.safetensors' not in []",
                            }
                        ],
                    }
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ComfyClient("http://comfy", http=http)
        with pytest.raises(RuntimeError) as error:
            await client.queue_prompt({"1": {}}, "client-1")

    assert str(error.value) == (
        "ComfyUI 工作流校验失败；ControlNetLoader：所选值不可用"
        "（control_net_name: 'missing.safetensors' not in []）"
    )
