import sys

import pytest

from app import main as app_main


def test_desktop_entry_starts_the_agent_on_loopback(monkeypatch) -> None:
    captured = {}

    def fake_run(application: str, **options) -> None:
        captured["application"] = application
        captured["options"] = options

    monkeypatch.setattr(app_main.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        sys, "argv", ["ai-art-agent-backend", "--port", "8007"]
    )

    app_main.run()

    assert captured == {
        "application": "app.main:app",
        "options": {"host": "127.0.0.1", "port": 8007},
    }


@pytest.mark.parametrize("port", [7999, 8100])
def test_desktop_entry_rejects_ports_outside_the_agent_range(
    monkeypatch, port: int
) -> None:
    monkeypatch.setattr(app_main.uvicorn, "run", lambda *args, **options: None)
    monkeypatch.setattr(
        sys, "argv", ["ai-art-agent-backend", "--port", str(port)]
    )

    with pytest.raises(ValueError, match="8000.*8099"):
        app_main.run()
