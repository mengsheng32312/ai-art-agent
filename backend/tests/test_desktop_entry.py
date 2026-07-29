from app import main as app_main


def test_desktop_entry_starts_the_agent_on_loopback(monkeypatch) -> None:
    captured = {}

    def fake_run(application: str, **options) -> None:
        captured["application"] = application
        captured["options"] = options

    monkeypatch.setattr(app_main.uvicorn, "run", fake_run)

    app_main.run()

    assert captured == {
        "application": "app.main:app",
        "options": {"host": "127.0.0.1", "port": 8000},
    }
