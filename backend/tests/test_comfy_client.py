import httpx
import pytest

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
