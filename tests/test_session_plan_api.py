from fastapi.testclient import TestClient

from app.api.routes import state_manager
from app.main import app


def test_session_and_plan_endpoints_work_after_chat():
    client = TestClient(app)
    chat_resp = client.post("/chat", json={"message": "查下杭州酒店"})
    session_id = chat_resp.json()["session_id"]

    session_resp = client.get(f"/session/{session_id}")
    plan_resp = client.get(f"/plan/{session_id}")

    assert session_resp.status_code == 200
    assert plan_resp.status_code == 200
    assert session_resp.json()["session_id"] == session_id
    plan_data = plan_resp.json()
    assert (
        "transport_plan" in plan_data
        or "hotel_plan" in plan_data
        or "itinerary_plan" in plan_data
    )


def test_plan_endpoint_fallbacks_to_last_plan_when_current_plan_missing():
    client = TestClient(app)
    chat_resp = client.post("/chat", json={"message": "帮我查上海到杭州的交通"})
    session_id = chat_resp.json()["session_id"]

    # 模拟 current_plans 被清理，但会话中仍保存了 last_plan。
    state_manager.current_plans.pop(session_id, None)

    plan_resp = client.get(f"/plan/{session_id}")
    assert plan_resp.status_code == 200
    assert "transport_plan" in plan_resp.json()


def test_revise_plan_returns_404_for_missing_session():
    client = TestClient(app)
    response = client.post(
        "/plan/s-missing/revise",
        json={"updates": {"budget": {"max": 1200}, "hotel_preferences": {"stars": 4}}},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "SESSION_NOT_FOUND"
    assert body["message"] == "session not found"


def test_revise_plan_updates_state_and_returns_new_plan():
    client = TestClient(app)
    chat_resp = client.post("/chat", json={"message": "帮我规划杭州两日游"})
    session_id = chat_resp.json()["session_id"]

    response = client.post(
        f"/plan/{session_id}/revise",
        json={
            "updates": {
                "budget": {"max": 1500},
                "hotel_preferences": {"stars": 4, "near": "西湖"},
                "pace_preference": "relaxed",
            }
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert isinstance(data["updated_plan"], dict)
    assert data["response"]
    assert state_manager.trip_states[session_id].budget == {"max": 1500}
    assert state_manager.trip_states[session_id].hotel_preferences == {"stars": 4, "near": "西湖"}
    assert state_manager.trip_states[session_id].pace_preference == "relaxed"
    assert data["updated_plan"]["hotel_plan"] is not None
