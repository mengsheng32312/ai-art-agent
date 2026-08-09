import re
from pathlib import Path
from typing import Any, Literal
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
PREVIEW_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MODEL_FOLDER_KINDS: dict[str, ModelKind] = {
    "checkpoints": "checkpoint",
    "diffusion_models": "checkpoint",
    "unet": "checkpoint",
    "loras": "lora",
    "controlnet": "controlnet",
    "vae": "vae",
}

VIDEO_KEYWORDS = (
    "motion",
    "animatediff",
    "animate",
    "mm_sd",
    "svd",
    "stable video",
    "video",
    "wan",
    "wan2",
    "hunyuan",
    "mochi",
    "ltx",
    "ltxv",
    "cogvideo",
    "cvg",
    "t2v",
    "i2v",
    "cosmos",
    "opensora",
    "tora",
    "seine",
    "vdu",
    "imagetovideo",
    "image to video",
    "videogen",
    "framerf",
    "vchitect",
    "sora",
    "frame",
    "framepack",
    "interp",
    "temporal",
)

TYPE_TO_KIND: dict[str, ModelKind] = {
    "checkpoint": "checkpoint",
    "diffusion_model": "checkpoint",
    "lora": "lora",
    "motion lora": "lora",
    "controlnet": "controlnet",
    "T2I-Adapter": "controlnet",
    "IP-Adapter": "controlnet",
    "instantid": "controlnet",
    "ipadapter": "controlnet",
    "VAE": "vae",
}


def infer_usage(text: str) -> Literal["image", "video"]:
    lowered = text.lower()
    pattern = re.compile(
        r"(?<![a-z0-9])(" + "|".join(re.escape(k) for k in VIDEO_KEYWORDS) + r")(?![a-z0-9])"
    )
    return "video" if pattern.search(lowered) else "image"


def model_id(kind: ModelKind, filename: str, source: str) -> str:
    return f"{source}:{kind}:{quote(filename, safe='')}"


def model_name(filename: str) -> str:
    return Path(filename).stem


def find_preview_image(model_file: Path) -> Path | None:
    """按 ComfyUI 惯例查找模型同目录的同名预览图（model.safetensors.png 或 model.png）。"""
    candidates = [Path(f"{model_file}{ext}") for ext in PREVIEW_EXTENSIONS]
    stem = model_file.with_suffix("")
    candidates += [Path(f"{stem}{ext}") for ext in PREVIEW_EXTENSIONS]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def resolve_local_model_root(config: AppConfig) -> Path | None:
    raw_path = config.local_model_path or config.comfyui_path
    if not raw_path:
        return None

    selected = Path(raw_path)
    if selected.name.lower() == "models":
        return selected

    candidates = [selected, selected / "models", selected / "ComfyUI" / "models"]
    for candidate in candidates:
        if candidate.is_dir() and any(
            (candidate / folder).is_dir() for folder in MODEL_FOLDER_KINDS
        ):
            return candidate
    return next((candidate for candidate in candidates[1:] if candidate.is_dir()), selected)


def scan_local_models(config: AppConfig) -> list[ModelItem]:
    root = resolve_local_model_root(config)
    if not root or not root.is_dir():
        return []

    items: list[ModelItem] = []
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.suffix.lower() not in MODEL_EXTENSIONS:
            continue
        relative = file.relative_to(root)
        folder = relative.parts[0].lower() if len(relative.parts) > 1 else ""
        kind = MODEL_FOLDER_KINDS.get(folder, "other")
        preview = find_preview_image(file)
        items.append(
            ModelItem(
                id=model_id(kind, str(relative), "local"),
                name=model_name(file.name),
                kind=kind,
                usage=infer_usage(str(relative)),
                filename=file.name,
                source="local",
                installed=True,
                path=str(file),
                preview_url=f"local:{preview}" if preview else None,
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
                    usage=infer_usage(filename),
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
    model_type = str(item.get("type") or "").strip()
    if model_type in TYPE_TO_KIND:
        return TYPE_TO_KIND[model_type]
    text = " ".join(str(item.get(key, "")) for key in ("type", "category", "save_path", "filename", "name")).lower()
    if "lora" in text:
        return "lora"
    if "vae" in text:
        return "vae"
    if "control" in text:
        return "controlnet"
    return "other"


def normalize_manager_model(item: dict[str, Any], installed_files: set[str]) -> ModelItem | None:
    filename = str(item.get("filename") or item.get("file_name") or item.get("name") or "").strip()
    if not filename:
        return None
    kind = infer_kind(item)
    return ModelItem(
        id=model_id(kind, filename, "manager"),
        name=str(item.get("name") or model_name(filename)),
        kind=kind,
        usage=infer_usage(
            " ".join(
                str(item.get(key, ""))
                for key in (
                    "type",
                    "category",
                    "base",
                    "save_path",
                    "filename",
                    "name",
                    "description",
                )
            )
        ),
        filename=filename,
        source="manager",
        installed=filename in installed_files,
        description=str(item.get("description") or item.get("title") or "ComfyUI Manager 模型库"),
        preview_url=item.get("image") or item.get("preview") or item.get("cover"),
        size_label=item.get("size") or item.get("size_label"),
        reference_url=item.get("reference"),
    )


async def build_model_catalog(config: AppConfig, client: ComfyClient) -> ModelCatalogResponse:
    local_files = scan_local_models(config)
    installed_files = {item.filename for item in local_files}
    connected = False
    manager_available = False
    message = "请先连接 ComfyUI"
    remote_models: list[ModelItem] = []
    online_models: list[ModelItem] = []

    try:
        await client.check_status()
        connected = True
        message = "ComfyUI 已连接"
        comfy_models = await list_comfy_models(client, local_files)
        preview_by_filename = {
            item.filename: item.preview_url
            for item in local_files
            if item.preview_url
        }
        for item in comfy_models:
            if item.filename in preview_by_filename and not item.preview_url:
                item.preview_url = preview_by_filename[item.filename]
        remote_models = comfy_models
        installed_files.update(item.filename for item in remote_models)
    except Exception as exc:
        return ModelCatalogResponse(
            connected=False,
            manager_available=False,
            message=str(exc),
            remote_models=[],
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
        remote_models=remote_models,
        local_models=local_files,
        online_models=online_models,
    )


async def request_manager_download(
    model_id_value: str,
    config: AppConfig,
    client: ComfyClient,
    destination: Literal["remote", "local"] = "local",
) -> ModelItem:
    local_files = scan_local_models(config)
    installed_files = {item.filename for item in local_files}
    try:
        manager_data = await client.manager_model_list()
    except Exception as exc:
        raise LookupError("ComfyUI Manager 不可用或未安装，无法浏览在线模型库") from exc
    for raw in manager_items_payload(manager_data):
        model = normalize_manager_model(raw, installed_files)
        if model and model.id == model_id_value:
            if config.mode == "local" or destination == "remote":
                await client.manager_install_model(raw)
            else:
                model_root = resolve_local_model_root(config)
                if not model_root:
                    raise ValueError("请先在连接设置中填写本地模型目录")
                url = str(raw.get("url") or "").strip()
                if not url:
                    raise ValueError("该模型没有直链下载地址，无法下载到本地")
                folder = str(raw.get("save_path") or MODEL_DIRS[model.kind].name).strip("/")
                destination_dir = model_root / folder
                await client.download_model_file(url, model.filename, destination_dir)
            return model

    raise LookupError("模型不存在或 ComfyUI Manager 不可用")
