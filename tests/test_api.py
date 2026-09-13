from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from demandiq.api.app import create_app
from demandiq.config import Settings


def test_liveness_without_database():
    engine = create_engine("postgresql+psycopg://localhost:1/unreachable")
    with TestClient(create_app(Settings(_env_file=None), engine)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/v1/health").status_code == 200
        schema = client.get("/openapi.json").json()
        assert "/api/v1/sales" in schema["paths"]
        assert all("post" not in methods for methods in schema["paths"].values())
        response = client.get("/api/v1/sales", params={"item_id": "../bad"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert "input" not in str(response.json()["error"]["details"])
        assert client.get("/api/v1/loads/not-a-uuid").status_code == 422
        assert client.get("/unknown").json()["error"]["code"] == "not_found"
    engine.dispose()


def test_database_errors_are_sanitized(monkeypatch):
    engine = create_engine("postgresql+psycopg://localhost:1/unreachable")

    def unavailable():
        raise OperationalError("sensitive statement", {}, Exception("sensitive connection"))

    monkeypatch.setattr(engine, "connect", unavailable)
    with TestClient(create_app(Settings(_env_file=None), engine)) as client:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert "sensitive" not in response.text
        assert client.get("/health").status_code == 200
    engine.dispose()
