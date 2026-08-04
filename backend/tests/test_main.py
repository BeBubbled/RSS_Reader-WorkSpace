from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings


def make_client() -> TestClient:
    app = main_module.create_app(
        Settings(
            admin_username="reader",
            admin_password="correct-password",
            app_session_secret="a-safe-test-secret-that-is-long-enough",
            database_url="postgresql+asyncpg://unused",
            redis_url="redis://unused",
        )
    )
    return TestClient(app)


def login(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "reader", "password": "correct-password"})
    assert response.status_code == 200


def test_health_does_not_require_dependencies() -> None:
    client = make_client()
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_reports_503_when_a_required_dependency_is_down(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "database_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(main_module, "redis_ready", AsyncMock(return_value=False))
    response = make_client().get("/ready")
    assert response.status_code == 503
    assert response.json()["detail"] == {"database": True, "redis": False}


def test_ready_reports_success_when_dependencies_are_available(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "database_ready", AsyncMock(return_value=True))
    monkeypatch.setattr(main_module, "redis_ready", AsyncMock(return_value=True))
    assert make_client().get("/ready").json() == {"status": "ready"}


def test_protected_endpoint_rejects_anonymous_requests() -> None:
    response = make_client().get("/api/app/status")
    assert response.status_code == 401


def test_login_rejects_invalid_credentials_without_session_cookie() -> None:
    response = make_client().post("/api/auth/login", json={"username": "reader", "password": "wrong"})
    assert response.status_code == 401
    assert "rss_ai_session" not in response.headers.get("set-cookie", "")


def test_login_me_and_logout_flow() -> None:
    client = make_client()
    login(client)
    cookie = client.cookies.get("rss_ai_session")
    assert cookie
    assert client.get("/api/auth/me").json() == {"username": "reader"}
    logout = client.post("/api/auth/logout")
    assert logout.status_code == 204
    assert "rss_ai_session" in logout.headers["set-cookie"]
    assert client.get("/api/auth/me").status_code == 401
