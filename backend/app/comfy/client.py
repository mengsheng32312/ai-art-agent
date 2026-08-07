from typing import Any
from pathlib import Path

import httpx


class ComfyUnavailableError(RuntimeError):
    """远程 ComfyUI 不可达（例如隧道断开或源站已停止）。"""


def _unavailable_error(exc: Exception) -> ComfyUnavailableError:
    if isinstance(exc, httpx.ConnectTimeout):
        return ComfyUnavailableError(
            "连接远程 ComfyUI 超时：网络较慢或隧道响应异常，请稍后重试"
        )
    if isinstance(exc, httpx.ConnectError):
        return ComfyUnavailableError(
            f"无法连接远程 ComfyUI：{exc}"
        )
    return ComfyUnavailableError(str(exc))


class ComfyClient:
    def __init__(self, base_url: str, http: httpx.AsyncClient | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            if self.http:
                response = await self.http.request(
                    method, f"{self.base_url}{path}", **kwargs
                )
            else:
                async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
                    response = await client.request(
                        method, f"{self.base_url}{path}", **kwargs
                    )
        except httpx.TimeoutException as exc:
            raise _unavailable_error(exc) from exc
        except httpx.ConnectError as exc:
            raise _unavailable_error(exc) from exc
        if response.status_code == 530:
            raise ComfyUnavailableError(
                "远程 ComfyUI 暂时不可用：连接隧道已断开，请重新运行 Colab 并更新 API 地址"
            )
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
        response = await self._request(
            "GET", "/externalmodel/getlist", params={"mode": "default"}
        )
        return response.json()

    async def manager_install_model(self, model: Any) -> None:
        # ComfyUI-Manager 要求请求体直接就是模型元数据，而不是包一层 {"model": ...}。
        await self._request("POST", "/manager/queue/install_model", json=model)
        # 任务入队后需要手动启动队列 worker，否则下载不会开始。
        await self._request("POST", "/manager/queue/start")

    async def manager_queue_status(self) -> dict[str, Any]:
        response = await self._request("GET", "/manager/queue/status")
        return response.json()

    async def download_model_file(
        self, url: str, filename: str, destination_dir: Path
    ) -> Path:
        """从模型直链 URL 流式下载模型文件到本地目录。"""
        safe_name = Path(filename).name
        destination = Path(destination_dir) / safe_name
        timeout = httpx.Timeout(connect=30, read=600, write=60, pool=10)
        if self.http:
            async with self.http.stream(
                "GET", url, timeout=timeout, follow_redirects=True
            ) as response:
                response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        file.write(chunk)
            return destination
        async with httpx.AsyncClient(timeout=timeout, trust_env=True) as client:
            async with client.stream("GET", url, follow_redirects=True) as response:
                response.raise_for_status()
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        file.write(chunk)
            return destination

    async def queue_prompt(self, workflow: dict[str, Any], client_id: str) -> str:
        response = await self._request(
            "POST", "/prompt", json={"prompt": workflow, "client_id": client_id}
        )
        return response.json()["prompt_id"]

    async def history(self, prompt_id: str) -> dict:
        response = await self._request("GET", f"/history/{prompt_id}")
        return response.json()

    async def queue(self) -> dict:
        response = await self._request("GET", "/queue")
        return response.json()
