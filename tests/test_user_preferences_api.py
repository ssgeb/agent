from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _register_and_login(client: TestClient, prefix: str) -> str:
    username = _unique(prefix)
    email = f"{username}@example.com"
    register = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "pass12345"},
    )
    assert register.status_code == 201

    login = client.post("/auth/login", json={"identifier": email, "password": "pass12345"})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_preferences_require_login():
    client = TestClient(app)

    response = client.get("/preferences")

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHENTICATED"


def test_user_can_save_and_read_own_preferences():
    client = TestClient(app)
    token = _register_and_login(client, "pref-owner")

    payload = {
        "budget": {"max": 2200},
        "hotel_preferences": {"stars": 4, "near": "西湖"},
        "transport_preferences": {"mode": "train"},
        "attraction_preferences": {"theme": "family"},
        "pace_preference": "relaxed",
        "must_visit_places": ["西湖"],
        "excluded_places": ["排队太久的项目"],
        "notes": ["少走路"],
    }

    save = client.put(
        "/preferences",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert save.status_code == 200
    assert save.json()["preferences"] == payload

    read = client.get("/preferences", headers={"Authorization": f"Bearer {token}"})

    assert read.status_code == 200
    assert read.json()["preferences"] == payload


def test_preferences_are_isolated_between_users():
    client = TestClient(app)
    alice_token = _register_and_login(client, "pref-alice")
    bob_token = _register_and_login(client, "pref-bob")

    save = client.put(
        "/preferences",
        headers={"Authorization": f"Bearer {alice_token}"},
        json={"budget": {"max": 1800}, "pace_preference": "relaxed"},
    )
    assert save.status_code == 200

    bob_read = client.get("/preferences", headers={"Authorization": f"Bearer {bob_token}"})

    assert bob_read.status_code == 200
    assert bob_read.json()["preferences"]["budget"] is None
    assert bob_read.json()["preferences"]["pace_preference"] is None


def test_saved_preferences_seed_new_async_chat_session():
    client = TestClient(app)
    token = _register_and_login(client, "pref-chat")
    payload = {
        "budget": {"max": 3200},
        "hotel_preferences": {"stars": 5, "near": "外滩"},
        "transport_preferences": {"mode": "flight"},
        "attraction_preferences": {"theme": "citywalk"},
        "pace_preference": "compact",
        "must_visit_places": ["外滩"],
        "excluded_places": ["夜店"],
        "notes": ["希望交通少换乘"],
    }
    client.put("/preferences", headers={"Authorization": f"Bearer {token}"}, json=payload)

    task_resp = client.post(
        "/chat/async",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "帮我规划上海三日游"},
    )

    assert task_resp.status_code == 202

    from app.api import routes

    session_id = task_resp.json()["session_id"]
    trip_state = routes.state_manager.trip_states[session_id]
    assert trip_state.budget == payload["budget"]
    assert trip_state.hotel_preferences == payload["hotel_preferences"]
    assert trip_state.transport_preferences == payload["transport_preferences"]
    assert trip_state.attraction_preferences == payload["attraction_preferences"]
    assert trip_state.pace_preference == payload["pace_preference"]
    assert trip_state.must_visit_places == payload["must_visit_places"]
    assert trip_state.excluded_places == payload["excluded_places"]
    assert trip_state.notes == payload["notes"]


def test_revision_preference_updates_are_remembered():
    client = TestClient(app)
    token = _register_and_login(client, "pref-revise")
    chat_resp = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "帮我规划杭州两日游"},
    )
    assert chat_resp.status_code == 200
    session_id = chat_resp.json()["session_id"]

    revise = client.post(
        f"/plan/{session_id}/revise",
        headers={"Authorization": f"Bearer {token}"},
        json={"updates": {"budget": {"max": 1600}, "hotel_preferences": {"stars": 4}}},
    )

    assert revise.status_code == 200
    read = client.get("/preferences", headers={"Authorization": f"Bearer {token}"})
    assert read.json()["preferences"]["budget"] == {"max": 1600}
    assert read.json()["preferences"]["hotel_preferences"] == {"stars": 4}
