from typing import Any

import httpx


class ComfyClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if self.http:
            response = await self.http.request(method, f"{self.base_url}{path}", **kwargs)
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        response.raise_for_status()
        return response

    async def check_status(self) -> bool:
        await self._request("GET", "/system_stats")
        return True

    async def list_checkpoints(self) -> list[str]:
        response = await self._request("GET", "/object_info/CheckpointLoaderSimple")
        data = response.json()
        return data["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]

    async def object_info(self, node_name: str) -> dict[str, Any]:
        response = await self._request("GET", f"/object_info/{node_name}")
        return response.json()

    async def manager_model_list(self) -> Any:
        response = await self._request("GET", "/manager/model-list")
        return response.json()

    async def manager_install_model(self, model: Any) -> Any:
        response = await self._request("POST", "/manager/queue/install_model", json={"model": model})
        return response.json()

    async def queue_prompt(self, workflow: dict[str, Any], client_id: str) -> str:
        response = await self._request(
            "POST", "/prompt", json={"prompt": workflow, "client_id": client_id}
        )
        return response.json()["prompt_id"]

    async def history(self, prompt_id: str) -> dict:
        response = await self._request("GET", f"/history/{prompt_id}")
        return response.json()
