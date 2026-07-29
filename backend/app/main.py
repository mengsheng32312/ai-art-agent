from pathlib import Path
from collections.abc import Callable
from uuid import uuid4
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, status

from .comfy.client import ComfyClient
from .comfy.workflow import build_text_to_image_workflow
from .history import HistoryStore
from .schemas import ConnectionStatus, GenerationRequest, GenerationTask
from .settings import AppConfig, ConfigStore, default_data_dir


def create_app(
    data_dir: Path | None = None,
    comfy_factory: Callable[[str], ComfyClient] = ComfyClient,
) -> FastAPI:
    root = data_dir or default_data_dir()
    store = ConfigStore(root / "config.json")
    history = HistoryStore(root / "history.json")
    app = FastAPI(title="AI Art Agent", version="0.1.0")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config", response_model=AppConfig)
    def get_config() -> AppConfig:
        return store.load()

    @app.put("/api/config", response_model=AppConfig)
    def put_config(config: AppConfig) -> AppConfig:
        store.save(config)
        return config

    def comfy():
        return comfy_factory(store.load().api_url)

    @app.get("/api/comfy/status", response_model=ConnectionStatus)
    async def comfy_status() -> ConnectionStatus:
        try:
            await comfy().check_status()
            return ConnectionStatus(connected=True, message="ComfyUI 已连接")
        except Exception as exc:
            return ConnectionStatus(connected=False, message=str(exc))

    @app.get("/api/comfy/checkpoints", response_model=list[str])
    async def checkpoints() -> list[str]:
        try:
            return await comfy().list_checkpoints()
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
            prompt_id = await comfy().queue_prompt(
                build_text_to_image_workflow(request), task_id
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
        for item in history.list():
            if item.id == task_id:
                if item.prompt_id and item.status in {"queued", "running"}:
                    data = await comfy().history(item.prompt_id)
                    prompt = data.get(item.prompt_id)
                    if prompt:
                        images = [
                            image
                            for output in prompt.get("outputs", {}).values()
                            for image in output.get("images", [])
                        ]
                        if images:
                            item.status = "completed"
                            item.progress = 100
                            item.outputs = [
                                f"{store.load().api_url}/view?{urlencode(image)}"
                                for image in images
                            ]
                            history.upsert(item)
                        else:
                            item.status = "running"
                return item
        raise HTTPException(status_code=404, detail="任务不存在")

    @app.get("/api/history", response_model=list[GenerationTask])
    def get_history() -> list[GenerationTask]:
        return history.list()

    return app


app = create_app()
