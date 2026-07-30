from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ai-art-agent",
        "version": "0.1.0",
    }


def test_desktop_webview_can_call_the_local_agent(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get(
        "/api/health", headers={"Origin": "http://tauri.localhost"}
    )

    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"
