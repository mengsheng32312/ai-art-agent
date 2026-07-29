import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    mode: Literal["local", "remote"] = "remote"
    comfyui_path: str | None = None
    api_url: str = Field(default="http://127.0.0.1:8188")


def default_data_dir() -> Path:
    base = Path(os.getenv("LOCALAPPDATA", Path.home() / ".ai-art-agent"))
    return base / "AI Art Agent"


class ConfigStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        return AppConfig.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(config.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
