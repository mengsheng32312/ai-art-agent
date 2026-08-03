from pathlib import Path
from typing import Any
from urllib.parse import quote

from .comfy.client import ComfyClient
from .schemas import ModelCatalogResponse, ModelItem, ModelKind
from .settings import AppConfig


MODEL_DIRS: dict[ModelKind, Path] = {
    "checkpoint": Path("models") / "checkpoints",
    "lora": Path("models") / "loras",
    "controlnet": Path("models") / "controlnet",
    "vae": Path("models") / "vae",
}

MODEL_NODES: dict[ModelKind, tuple[str, str]] = {
    "checkpoint": ("CheckpointLoaderSimple", "ckpt_name"),
    "lora": ("LoraLoader", "lora_name"),
    "vae": ("VAELoader", "vae_name"),
    "controlnet": ("ControlNetLoader", "control_net_name"),
}

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin"}


def model_id(kind: ModelKind, filename: str, source: str) -> str:
    return f"{source}:{kind}:{quote(filename, safe='')}"


def model_name(filename: str) -> str:
    return Path(filename).stem


def scan_local_models(config: AppConfig) -> list[ModelItem]:
    if not config.comfyui_path:
        return []

    root = Path(config.comfyui_path)
    items: list[ModelItem] = []
    for kind, relative_dir in MODEL_DIRS.items():
        directory = root / relative_dir
        if not directory.exists():
            continue
        for file in sorted(directory.rglob("*")):
            if not file.is_file() or file.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            items.append(
                ModelItem(
                    id=model_id(kind, file.name, "local"),
                    name=model_name(file.name),
                    kind=kind,
                    filename=file.name,
                    source="local",
                    installed=True,
                    path=str(file),
                    description="本地 ComfyUI 模型文件",
                )
            )
    return items


async def list_comfy_models(client: ComfyClient, local_models: list[ModelItem]) -> list[ModelItem]:
    local_by_filename = {item.filename: item for item in local_models}
    items: list[ModelItem] = []
    for kind, (node_name, input_name) in MODEL_NODES.items():
        try:
            data = await client.object_info(node_name)
            names = data[node_name]["input"]["required"][input_name][0]
        except Exception:
            continue

        for filename in names:
            local = local_by_filename.get(filename)
            items.append(
                ModelItem(
                    id=model_id(kind, filename, "comfyui"),
                    name=model_name(filename),
                    kind=kind,
                    filename=filename,
                    source="comfyui",
                    installed=True,
                    path=local.path if local else None,
                    description="ComfyUI 当前可用模型",
                )
            )
    return items


def manager_items_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("models", "model_list", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def infer_kind(item: dict[str, Any]) -> ModelKind:
    text = " ".join(str(item.get(key, "")) for key in ("type", "category", "save_path", "filename", "name")).lower()
    if "lora" in text:
        return "lora"
    if "vae" in text:
        return "vae"
    if "control" in text:
        return "controlnet"
    return "checkpoint"


def normalize_manager_model(item: dict[str, Any], installed_files: set[str]) -> ModelItem | None:
    filename = str(item.get("filename") or item.get("file_name") or item.get("name") or "").strip()
    if not filename:
        return None
    kind = infer_kind(item)
    return ModelItem(
        id=model_id(kind, filename, "manager"),
        name=str(item.get("name") or model_name(filename)),
        kind=kind,
        filename=filename,
        source="manager",
        installed=filename in installed_files,
        description=str(item.get("description") or item.get("title") or "ComfyUI Manager 模型库"),
        preview_url=item.get("image") or item.get("preview") or item.get("cover"),
        size_label=item.get("size") or item.get("size_label"),
    )


async def build_model_catalog(config: AppConfig, client: ComfyClient) -> ModelCatalogResponse:
    local_files = scan_local_models(config)
    installed_files = {item.filename for item in local_files}
    connected = False
    manager_available = False
    message = "请先连接 ComfyUI"
    local_models = local_files
    online_models: list[ModelItem] = []

    try:
        await client.check_status()
        connected = True
        message = "ComfyUI 已连接"
        comfy_models = await list_comfy_models(client, local_files)
        if comfy_models:
            local_models = comfy_models
    except Exception as exc:
        return ModelCatalogResponse(
            connected=False,
            manager_available=False,
            message=str(exc),
            local_models=[],
            online_models=[],
        )

    try:
        manager_data = await client.manager_model_list()
        manager_available = True
        for raw in manager_items_payload(manager_data):
            model = normalize_manager_model(raw, installed_files)
            if model:
                online_models.append(model)
    except Exception:
        manager_available = False

    return ModelCatalogResponse(
        connected=connected,
        manager_available=manager_available,
        message=message,
        local_models=local_models,
        online_models=online_models,
    )


async def request_manager_download(model_id_value: str, config: AppConfig, client: ComfyClient) -> ModelItem:
    if not config.comfyui_path:
        raise ValueError("请先选择 ComfyUI 安装目录")

    local_files = scan_local_models(config)
    installed_files = {item.filename for item in local_files}
    manager_data = await client.manager_model_list()
    for raw in manager_items_payload(manager_data):
        model = normalize_manager_model(raw, installed_files)
        if model and model.id == model_id_value:
            await client.manager_install_model(raw)
            return model

    raise LookupError("模型不存在或 ComfyUI Manager 不可用")
