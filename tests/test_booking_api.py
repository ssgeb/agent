from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _register_and_login(client: TestClient):
    username = _unique("booker")
    email = f"{username}@example.com"
    password = "pass12345"

    register = client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert register.status_code == 201

    login = client.post(
        "/auth/login",
        json={"identifier": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_booking_record_create_and_list_flow():
    client = TestClient(app)
    token = _register_and_login(client)

    create_resp = client.post(
        "/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": "s-booking",
            "booking_type": "hotel",
            "item_name": "西湖景观酒店",
            "amount": 680,
            "currency": "CNY",
            "payload": {"plan_title": "杭州两日游", "source": "fake_booking"},
        },
    )

    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["booking_id"].startswith("b-")
    assert body["status"] == "CREATED"
    assert body["booking_type"] == "hotel"
    assert body["item_name"] == "西湖景观酒店"

    list_resp = client.get(
        "/bookings?limit=20",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_resp.status_code == 200
    assert list_resp.json()["bookings"][0]["booking_id"] == body["booking_id"]


def test_booking_record_list_can_filter_by_session():
    client = TestClient(app)
    token = _register_and_login(client)

    client.post(
        "/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": "s-target",
            "booking_type": "transport",
            "item_name": "高铁",
            "amount": 180,
            "currency": "CNY",
            "payload": {"mode": "train"},
        },
    )
    client.post(
        "/bookings",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "session_id": "s-other",
            "booking_type": "hotel",
            "item_name": "别的酒店",
            "amount": 520,
            "currency": "CNY",
            "payload": {"mode": "hotel"},
        },
    )

    resp = client.get(
        "/bookings?session_id=s-target",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    bookings = resp.json()["bookings"]
    assert len(bookings) == 1
    assert bookings[0]["session_id"] == "s-target"


def test_booking_endpoints_require_authentication():
    client = TestClient(app)

    create_resp = client.post(
        "/bookings",
        json={
            "session_id": "s-booking",
            "booking_type": "hotel",
            "item_name": "西湖景观酒店",
        },
    )
    assert create_resp.status_code == 401
    assert create_resp.json()["code"] == "UNAUTHENTICATED"

    list_resp = client.get("/bookings")
    assert list_resp.status_code == 401
    assert list_resp.json()["code"] == "UNAUTHENTICATED"
