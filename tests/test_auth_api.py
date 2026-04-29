from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _unique(value: str) -> str:
    return f"{value}-{uuid4().hex[:8]}"


def test_register_login_and_me_flow():
    client = TestClient(app)
    username = _unique("alice")
    email = f"{username}@example.com"

    register = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": "pass12345"},
    )

    assert register.status_code == 201
    assert register.json()["user"]["username"] == username
    assert "access_token" in register.json()
    assert "password" not in register.text

    login = client.post(
        "/auth/login",
        json={"identifier": email, "password": "pass12345"},
    )

    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["email"] == email


def test_register_rejects_duplicate_email():
    client = TestClient(app)
    unique = uuid4().hex[:8]
    payload = {
        "username": f"bob-{unique}",
        "email": f"bob-{unique}@example.com",
        "password": "pass12345",
    }

    first = client.post("/auth/register", json=payload)
    second = client.post("/auth/register", json={**payload, "username": "bobby"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["code"] == "USER_ALREADY_EXISTS"


def test_login_rejects_wrong_password():
    client = TestClient(app)
    unique = uuid4().hex[:8]
    client.post(
        "/auth/register",
        json={
            "username": f"carol-{unique}",
            "email": f"carol-{unique}@example.com",
            "password": "pass12345",
        },
    )

    response = client.post(
        "/auth/login",
        json={"identifier": f"carol-{unique}@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
