from pathlib import Path

from app.settings import AppConfig, ConfigStore


def test_default_config_uses_local_comfy_api() -> None:
    assert AppConfig().api_url == "http://127.0.0.1:8188"


def test_config_round_trips_to_json(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    expected = AppConfig(mode="local", comfyui_path="D:/ComfyUI")

    store.save(expected)

    assert store.load() == expected
