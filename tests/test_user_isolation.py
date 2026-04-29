from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _register_and_login(client: TestClient, username: str, email: str, password: str = "pass12345") -> str:
    register = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert register.status_code == 201

    login = client.post("/auth/login", json={"identifier": email, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_bob_cannot_read_alices_task():
    client = TestClient(app)
    alice_name = _unique("alice")
    bob_name = _unique("bob")
    alice_token = _register_and_login(client, alice_name, f"{alice_name}@example.com")
    bob_token = _register_and_login(client, bob_name, f"{bob_name}@example.com")

    task_resp = client.post(
        "/chat/async",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"message": "帮我规划杭州两日游"},
    )

    assert task_resp.status_code == 202
    task_id = task_resp.json()["task_id"]

    bob_lookup = client.get(f"/task/{task_id}", headers={"Authorization": f"Bearer {bob_token}"})

    assert bob_lookup.status_code == 404
    assert bob_lookup.json()["code"] == "TASK_NOT_FOUND"


def test_bob_cannot_read_alices_plan_history():
    client = TestClient(app)
    alice_name = _unique("alice")
    bob_name = _unique("bob")
    alice_token = _register_and_login(client, alice_name, f"{alice_name}@example.com")
    bob_token = _register_and_login(client, bob_name, f"{bob_name}@example.com")

    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"message": "帮我规划杭州两日游"},
    )

    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    bob_lookup = client.get(f"/plan/{session_id}/history", headers={"Authorization": f"Bearer {bob_token}"})

    assert bob_lookup.status_code == 404
    body = bob_lookup.json()
    assert body["code"] == "PLAN_NOT_FOUND"
    assert "history" not in body


def test_invalid_bearer_token_on_plan_history_returns_401():
    client = TestClient(app)
    owner_name = _unique("owner")
    owner_token = _register_and_login(client, owner_name, f"{owner_name}@example.com")

    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"message": "帮我规划杭州两日游"},
    )
    session_id = chat_resp.json()["session_id"]

    response = client.get(
        f"/plan/{session_id}/history",
        headers={"Authorization": "Bearer definitely-not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_anonymous_request_does_not_return_user_owned_persisted_history():
    client = TestClient(app)
    owner_name = _unique("owner")
    owner_token = _register_and_login(client, owner_name, f"{owner_name}@example.com")

    task_resp = client.post(
        "/chat/async",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"message": "帮我规划杭州两日游"},
    )
    assert task_resp.status_code == 202

    consume_resp = client.post("/tasks/consume-batch?max_tasks=10&blocking_timeout_seconds=0.01")
    assert consume_resp.status_code == 200

    from app.api import routes

    session_id = routes.task_repository.get_task(task_resp.json()["task_id"]).session_id
    routes.state_manager.plan_histories.pop(session_id, None)

    response = client.get(f"/plan/{session_id}/history")

    assert response.status_code == 404
    assert response.json()["code"] == "PLAN_NOT_FOUND"


def test_authenticated_owner_can_read_fresh_sync_plan_history():
    client = TestClient(app)
    owner_name = _unique("owner")
    owner_token = _register_and_login(client, owner_name, f"{owner_name}@example.com")

    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"message": "帮我规划杭州两日游"},
    )
    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    response = client.get(
        f"/plan/{session_id}/history",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert response.json()["history"]


def test_bob_cannot_revise_alices_sync_session():
    client = TestClient(app)
    alice_name = _unique("alice")
    bob_name = _unique("bob")
    alice_token = _register_and_login(client, alice_name, f"{alice_name}@example.com")
    bob_token = _register_and_login(client, bob_name, f"{bob_name}@example.com")

    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"message": "甯垜瑙勫垝鏉窞涓ゆ棩娓?"},
    )
    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    response = client.post(
        f"/plan/{session_id}/revise",
        headers={"Authorization": f"Bearer {bob_token}"},
        json={"updates": {"budget": {"max": 1200}}},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "PLAN_NOT_FOUND"


def test_owner_can_revise_own_sync_session():
    client = TestClient(app)
    owner_name = _unique("owner")
    owner_token = _register_and_login(client, owner_name, f"{owner_name}@example.com")

    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"message": "甯垜瑙勫垝鏉窞涓ゆ棩娓?"},
    )
    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    response = client.post(
        f"/plan/{session_id}/revise",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"updates": {"budget": {"max": 1400}}},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == session_id
    assert response.json()["updated_plan"]


def test_owner_can_read_persisted_history_after_owner_map_loss():
    client = TestClient(app)
    alice_name = _unique("alice")
    bob_name = _unique("bob")
    alice_token = _register_and_login(client, alice_name, f"{alice_name}@example.com")
    bob_token = _register_and_login(client, bob_name, f"{bob_name}@example.com")

    task_resp = client.post(
        "/chat/async",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"message": "甯垜瑙勫垝鏉窞涓ゆ棩娓?"},
    )
    assert task_resp.status_code == 202

    consume_resp = client.post("/tasks/consume-once")
    assert consume_resp.status_code == 200
    assert consume_resp.json()["processed"] is True

    from app.api import routes

    task_id = task_resp.json()["task_id"]
    session_id = routes.task_repository.get_task(task_id).session_id
    routes.session_owner_ids.pop(session_id, None)
    routes.state_manager.plan_histories.pop(session_id, None)
    routes.state_manager.current_plans.pop(session_id, None)

    alice_lookup = client.get(
        f"/plan/{session_id}/history",
        headers={"Authorization": f"Bearer {alice_token}"},
    )
    assert alice_lookup.status_code == 200
    assert alice_lookup.json()["session_id"] == session_id
    assert alice_lookup.json()["history"]

    bob_lookup = client.get(
        f"/plan/{session_id}/history",
        headers={"Authorization": f"Bearer {bob_token}"},
    )
    assert bob_lookup.status_code == 404
    assert bob_lookup.json()["code"] == "PLAN_NOT_FOUND"


def test_ownerless_anonymous_history_is_legacy_anonymous_only():
    client = TestClient(app)
    session_resp = client.post("/chat", json={"message": "帮我规划杭州两日游"})
    assert session_resp.status_code == 200
    session_id = session_resp.json()["session_id"]

    anonymous_resp = client.get(f"/plan/{session_id}/history")
    assert anonymous_resp.status_code == 200
    assert anonymous_resp.json()["session_id"] == session_id
    assert anonymous_resp.json()["history"]

    owner_name = _unique("owner")
    owner_token = _register_and_login(client, owner_name, f"{owner_name}@example.com")
    auth_resp = client.get(
        f"/plan/{session_id}/history",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert auth_resp.status_code == 404
    assert auth_resp.json()["code"] == "PLAN_NOT_FOUND"
