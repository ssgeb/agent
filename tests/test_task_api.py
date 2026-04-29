from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _get_auth_headers(client: TestClient) -> dict:
    """注册并登录用户，返回认证头。"""
    unique = uuid4().hex[:8]
    username = f"user-{unique}"
    email = f"{username}@example.com"
    password = "pass12345"

    client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    login_resp = client.post(
        "/auth/login",
        json={"identifier": email, "password": password},
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_returns_task_id_for_async_flow():
    client = TestClient(app)
    headers = _get_auth_headers(client)
    response = client.post("/chat/async", json={"message": "帮我规划杭州两日游"}, headers=headers)

    assert response.status_code == 202
    assert response.json()["task_id"]
    assert response.json()["status"] == "PENDING"


def test_chat_async_persists_request_id_in_task_payload():
    from app.api import routes

    client = TestClient(app)
    headers = _get_auth_headers(client)
    response = client.post("/chat/async", json={"message": "帮我规划杭州两日游"}, headers=headers)

    assert response.status_code == 202
    request_id = response.headers["X-Request-ID"]
    task = routes.task_repository.get_task(response.json()["task_id"])
    assert task.payload_json["request_id"] == request_id


def test_task_query_endpoint_returns_status():
    client = TestClient(app)
    headers = _get_auth_headers(client)
    task_id = client.post("/chat/async", json={"message": "上海到杭州两日酒店"}, headers=headers).json()["task_id"]

    response = client.get(f"/task/{task_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["task_id"] == task_id


def test_task_steps_endpoint_after_consume_once():
    client = TestClient(app)
    headers = _get_auth_headers(client)
    task_id = client.post("/chat/async", json={"message": "上海到杭州两日酒店"}, headers=headers).json()["task_id"]

    # 队列可能存在历史任务，循环消费直到当前 task 进入终态。
    for _ in range(10):
        consume_resp = client.post("/tasks/consume-once")
        assert consume_resp.status_code == 200
        assert consume_resp.json()["consumed"] is True
        status = client.get(f"/task/{task_id}", headers=headers).json()["status"]
        if status == "SUCCEEDED":
            break
    assert client.get(f"/task/{task_id}", headers=headers).json()["status"] == "SUCCEEDED"

    steps_resp = client.get(f"/task/{task_id}/steps", headers=headers)
    assert steps_resp.status_code == 200
    assert steps_resp.json()["task_id"] == task_id
    assert len(steps_resp.json()["steps"]) >= 1


def test_plan_history_endpoint_returns_list():
    client = TestClient(app)
    chat_resp = client.post("/chat", json={"message": "帮我规划杭州两日游"})
    session_id = chat_resp.json()["session_id"]

    response = client.get(f"/plan/{session_id}/history?limit=5")

    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert isinstance(response.json()["history"], list)


def test_consume_batch_supports_multi_session_tasks():
    client = TestClient(app)
    headers = _get_auth_headers(client)
    task_ids = []
    for message in ["上海到杭州两日酒店", "上海到杭州两日游", "上海到杭州两日景点"]:
        task_ids.append(client.post("/chat/async", json={"message": message}, headers=headers).json()["task_id"])

    consume_resp = client.post("/tasks/consume-batch?max_tasks=10&blocking_timeout_seconds=0.01")
    assert consume_resp.status_code == 200
    assert consume_resp.json()["consumed_count"] >= len(task_ids)

    for task_id in task_ids:
        task_resp = client.get(f"/task/{task_id}", headers=headers)
        assert task_resp.status_code == 200
        assert task_resp.json()["status"] in {"SUCCEEDED", "WAITING_INPUT"}


def test_task_cancel_endpoint_changes_status():
    client = TestClient(app)
    headers = _get_auth_headers(client)
    task_id = client.post("/chat/async", json={"message": "上海到杭州两日酒店"}, headers=headers).json()["task_id"]

    cancel_resp = client.post(f"/task/{task_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["task_id"] == task_id
    assert cancel_resp.json()["canceled"] is True
    assert cancel_resp.json()["status"] == "CANCELED"


def test_recover_endpoint_uses_configured_stale_seconds(monkeypatch):
    from app.api import routes

    class RecordingWorker:
        def __init__(self) -> None:
            self.stale_seconds = None

        def resume_incomplete_tasks(self, *, stale_seconds=None):
            self.stale_seconds = stale_seconds
            return ["t-recovered"]

    worker = RecordingWorker()
    monkeypatch.setattr(routes, "task_worker", worker)
    monkeypatch.setattr(routes.settings, "task_recovery_stale_seconds", 123)

    client = TestClient(app)
    response = client.post("/tasks/recover")

    assert response.status_code == 200
    assert response.json() == {"recovered_task_ids": ["t-recovered"], "recovered_count": 1}
    assert worker.stale_seconds == 123


def test_consume_once_reports_consumed_and_processed_for_bad_payload(monkeypatch):
    client = TestClient(app)
    from app.api import routes

    monkeypatch.setattr(routes.task_queue, "dequeue", lambda: {"session_id": "s-bad-payload"})
    response = client.post("/tasks/consume-once")

    assert response.status_code == 200
    assert response.json()["consumed"] is True
    assert response.json()["processed"] is False
    assert response.json()["task_id"] is None


def test_task_endpoints_return_404_for_missing_task():
    client = TestClient(app)
    headers = _get_auth_headers(client)

    task_resp = client.get("/task/t-missing", headers=headers)
    assert task_resp.status_code == 404
    assert task_resp.json()["code"] == "TASK_NOT_FOUND"

    cancel_resp = client.post("/task/t-missing/cancel", headers=headers)
    assert cancel_resp.status_code == 404
    assert cancel_resp.json()["code"] == "TASK_NOT_FOUND"

    steps_resp = client.get("/task/t-missing/steps", headers=headers)
    assert steps_resp.status_code == 404
    assert steps_resp.json()["code"] == "TASK_NOT_FOUND"
