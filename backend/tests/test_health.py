from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok(tmp_path) -> None:
    client = TestClient(create_app(data_dir=tmp_path))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
