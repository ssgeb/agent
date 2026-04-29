from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_session_and_plan():
    client = TestClient(app)
    response = client.post("/chat", json={"message": "帮我规划杭州两日游"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"]
    assert isinstance(data.get("updated_plan"), dict)
