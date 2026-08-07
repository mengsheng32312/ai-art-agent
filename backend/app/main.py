import argparse
from pathlib import Path
from collections.abc import Callable
from uuid import uuid4
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
import uvicorn

from .comfy.client import ComfyClient
from .comfy.resolver import install_fallback_resolver
from .comfy.workflow import build_text_to_image_workflow, build_text_to_video_workflow
from .history import HistoryStore
from .models import build_model_catalog, request_manager_download
from .schemas import (
    ConnectionStatus,
    GenerationRequest,
    GenerationTask,
    ManagerQueueStatus,
    ModelCatalogResponse,
    ModelDownloadRequest,
    ModelItem,
)
from .settings import AppConfig, ConfigStore, default_data_dir


install_fallback_resolver()


def create_app(
    data_dir: Path | None = None,
    comfy_factory: Callable[[str], ComfyClient] = ComfyClient,
) -> FastAPI:
    root = data_dir or default_data_dir()
    store = ConfigStore(root / "config.json")
    history = HistoryStore(root / "history.json")
    missing_polls: dict[str, int] = {}
    app = FastAPI(title="AI Art Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
            "http://127.0.0.1:1420",
            "http://localhost:1420",
        ],
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "ai-art-agent",
            "version": "0.1.0",
        }

    @app.get("/api/config", response_model=AppConfig)
    def get_config() -> AppConfig:
        return store.load()

    @app.put("/api/config", response_model=AppConfig)
    def put_config(config: AppConfig) -> AppConfig:
        store.save(config)
        return config

    def comfy():
        return comfy_factory(store.load().api_url)

    async def connection_status(config: AppConfig) -> ConnectionStatus:
        try:
            await comfy_factory(config.api_url).check_status()
            return ConnectionStatus(connected=True, message="ComfyUI 已连接")
        except Exception as exc:
            return ConnectionStatus(connected=False, message=str(exc))

    @app.get("/api/comfy/status", response_model=ConnectionStatus)
    async def comfy_status() -> ConnectionStatus:
        return await connection_status(store.load())

    @app.get("/api/comfy/view")
    async def comfy_view(
        filename: str, subfolder: str = "", type: str = "output"
    ) -> Response:
        """代理远程 ComfyUI 的 /view 图片，避免浏览器直连隧道不稳定。"""
        base = store.load().api_url.rstrip("/")
        params: dict[str, str] = {"filename": filename, "type": type}
        if subfolder:
            params["subfolder"] = subfolder
        try:
            async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
                response = await client.get(f"{base}/view", params=params)
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=503, detail=f"远程图片获取失败：{exc}"
            ) from exc
        if response.status_code == 530:
            raise HTTPException(
                status_code=503,
                detail="远程 ComfyUI 暂时不可用：连接隧道已断开，请重新运行 Colab 并更新 API 地址",
            )
        response.raise_for_status()
        return Response(
            content=response.content,
            media_type=response.headers.get(
                "content-type", "application/octet-stream"
            ),
        )

    @app.get("/api/comfy/local-model-image")
    def local_model_image(path: str) -> FileResponse:
        """返回本地 ComfyUI 模型目录中的预览图文件。"""
        config = store.load()
        if not config.comfyui_path:
            raise HTTPException(status_code=400, detail="未配置本地目录")
        root = Path(config.comfyui_path).resolve()
        image_path = Path(path).resolve()
        if image_path != root and root not in image_path.parents:
            raise HTTPException(status_code=403, detail="路径越界")
        if not image_path.is_file():
            raise HTTPException(status_code=404, detail="预览图不存在")
        return FileResponse(image_path)

    @app.post("/api/comfy/status", response_model=ConnectionStatus)
    async def check_candidate_comfy_status(config: AppConfig) -> ConnectionStatus:
        return await connection_status(config)

    @app.get("/api/comfy/checkpoints", response_model=list[str])
    async def checkpoints() -> list[str]:
        try:
            return await comfy().list_checkpoints()
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/comfy/video-models", response_model=list[str])
    async def video_models() -> list[str]:
        try:
            data = await comfy().object_info("ADE_AnimateDiffLoaderGen1")
            raw = data["ADE_AnimateDiffLoaderGen1"]["input"]["required"]["model_name"]
            if isinstance(raw, list) and len(raw) == 2 and isinstance(raw[1], dict):
                return raw[1].get("options", [])
            return raw[0] if isinstance(raw, list) else []
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/api/comfy/vae-models", response_model=list[str])
    async def vae_models() -> list[str]:
        try:
            data = await comfy().object_info("VAELoader")
            names = data["VAELoader"]["input"]["required"]["vae_name"][0]
            # "pixel_space" 不是真实 VAE，选中会导致输出原始潜变量（像素噪点）
            return [name for name in names if name != "pixel_space"]
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post(
        "/api/generations",
        response_model=GenerationTask,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_generation(request: GenerationRequest) -> GenerationTask:
        task_id = str(uuid4())
        try:
            workflow = (
                build_text_to_video_workflow(
                    request, output_prefix=f"AIArtAgent/{task_id}"
                )
                if request.media_type == "video"
                else build_text_to_image_workflow(
                    request, output_prefix=f"AIArtAgent/{task_id}"
                )
            )
            prompt_id = await comfy().queue_prompt(
                workflow,
                task_id,
            )
            task = GenerationTask(
                id=task_id,
                status="queued",
                request=request,
                prompt_id=prompt_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        history.upsert(task)
        return task

    @app.get("/api/generations/{task_id}", response_model=GenerationTask)
    async def get_generation(task_id: str) -> GenerationTask:
        def queue_contains(entries: list, prompt_id: str) -> bool:
            return any(
                (
                    isinstance(entry, (list, tuple))
                    and len(entry) > 1
                    and entry[1] == prompt_id
                )
                or (isinstance(entry, dict) and entry.get("prompt_id") == prompt_id)
                for entry in entries
            )

        for item in history.list():
            if item.id == task_id:
                if item.prompt_id and item.status in {"queued", "running"}:
                    client = comfy()
                    try:
                        data = await client.history(item.prompt_id)
                        prompt = data.get(item.prompt_id)
                        queue = await client.queue() if not prompt else None
                    except Exception as exc:
                        raise HTTPException(
                            status_code=502,
                            detail="暂时无法读取 ComfyUI 任务状态",
                        ) from exc
                    if prompt:
                        missing_polls.pop(item.id, None)
                        execution_error = next(
                            (
                                message[1]
                                for message in prompt.get("status", {}).get(
                                    "messages", []
                                )
                                if len(message) >= 2
                                and message[0] == "execution_error"
                                and isinstance(message[1], dict)
                            ),
                            None,
                        )
                        images = [
                            image
                            for output in prompt.get("outputs", {}).values()
                            for image in output.get("images", [])
                        ] + [
                            image
                            for output in prompt.get("outputs", {}).values()
                            for image in output.get("gifs", [])
                        ]
                        if execution_error:
                            item.status = "failed"
                            item.error = execution_error.get(
                                "exception_message", "ComfyUI execution failed"
                            )
                        elif images:
                            item.status = "completed"
                            item.progress = 100
                            item.outputs = [
                                f"{store.load().api_url.rstrip('/')}/view?{urlencode(image)}"
                                for image in images
                            ]
                        else:
                            item.status = "running"
                            item.progress = max(item.progress, 1)
                        history.upsert(item)
                    else:
                        if queue_contains(
                            queue.get("queue_running", []), item.prompt_id
                        ):
                            missing_polls.pop(item.id, None)
                            item.status = "running"
                            item.progress = max(item.progress, 1)
                            history.upsert(item)
                        elif queue_contains(
                            queue.get("queue_pending", []), item.prompt_id
                        ):
                            missing_polls.pop(item.id, None)
                            item.status = "queued"
                            history.upsert(item)
                        else:
                            missing_polls[item.id] = missing_polls.get(item.id, 0) + 1
                            if missing_polls[item.id] >= 3:
                                item.status = "failed"
                                item.error = (
                                    "任务已从 ComfyUI 队列消失，可能已取消或中断"
                                )
                                missing_polls.pop(item.id, None)
                                history.upsert(item)
                return item
        raise HTTPException(status_code=404, detail="任务不存在")

    @app.get("/api/history", response_model=list[GenerationTask])
    def get_history() -> list[GenerationTask]:
        return history.list()

    @app.delete("/api/history/{task_id}")
    def delete_history(task_id: str) -> dict[str, bool]:
        if not history.remove(task_id):
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True}

    @app.get("/api/models/catalog", response_model=ModelCatalogResponse)
    async def get_model_catalog() -> ModelCatalogResponse:
        return await build_model_catalog(store.load(), comfy())

    @app.post("/api/models/download", response_model=ModelItem)
    async def post_model_download(request: ModelDownloadRequest) -> ModelItem:
        config = store.load()
        try:
            return await request_manager_download(
                request.model_id, config, comfy(), request.destination
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"模型下载失败：{exc}") from exc

    @app.get("/api/models/manager/status", response_model=ManagerQueueStatus)
    async def get_manager_queue_status() -> ManagerQueueStatus:
        try:
            return await comfy().manager_queue_status()
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"获取远程下载状态失败：{exc}"
            ) from exc

    return app


app = create_app()


def desktop_port(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--port", type=int, default=8000)
    options, _ = parser.parse_known_args(argv)
    if not 8000 <= options.port <= 8099:
        raise ValueError("Agent 端口必须在 8000 到 8099 之间")
    return options.port


def run() -> None:
    uvicorn.run("app.main:app", host="127.0.0.1", port=desktop_port())
