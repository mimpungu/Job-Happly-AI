from fastapi.testclient import TestClient

from app.main import app


def test_health_retourne_ok() -> None:
    reponse = TestClient(app).get("/api/v1/health")

    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}
