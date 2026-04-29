from fastapi.testclient import TestClient

from app.api.routes import state_manager
from app.main import app


def test_missing_session_returns_unified_error_code_and_request_id_header():
    client = TestClient(app)

    response = client.get("/session/s-absent-001")

    assert response.status_code == 404
    assert response.headers["X-Request-ID"]

    body = response.json()
    assert body["code"] == "SESSION_NOT_FOUND"
    assert body["message"] == "session not found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_missing_plan_returns_unified_error_code_and_request_id_header():
    client = TestClient(app)
    session_id = "s-no-plan-001"
    state_manager.create_session(session_id)

    response = client.get(f"/plan/{session_id}")

    assert response.status_code == 404
    assert response.headers["X-Request-ID"]

    body = response.json()
    assert body["code"] == "PLAN_NOT_FOUND"
    assert body["message"] == "plan not found"
    assert body["request_id"] == response.headers["X-Request-ID"]
