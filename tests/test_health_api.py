from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.tools import AgentReachAdapter, AmapMcpAdapter


def test_health_endpoint_returns_ok_status():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "multi-agent-travel-planner",
    }


def test_ready_endpoint_reports_agent_reach_tooling():
    client = TestClient(app)

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"ready", "degraded"}
    assert body["database"]["available"] is True
    assert body["queue"]["mode"] in {"redis", "local"}
    assert body["tools"]["mode"] in {"agent_reach", "amap_mcp", "mock"}
    assert body["tools"]["agent_reach_enabled"] is True
    assert "amap_mcp_enabled" in body["tools"]
    assert "config" in body


def test_ready_endpoint_reports_unavailable_agent_reach_cli(monkeypatch):
    class UnavailableFetcher:
        def is_available(self):
            return False

        async def __call__(self, operation: str, payload: dict):
            return []

    client = TestClient(app)
    monkeypatch.setattr(routes, "tool_provider", AgentReachAdapter(fetcher=UnavailableFetcher()))

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["tools"]["agent_reach_available"] is False
    assert body["tools"]["degraded"] is True
    assert "agent_reach_cli_unavailable" in body["config"]["warnings"]


def test_ready_endpoint_reports_unavailable_amap_mcp(monkeypatch):
    class UnavailableClient:
        def is_available(self):
            return False

        async def __call__(self, tool_name: str, arguments: dict):
            return {}

    client = TestClient(app)
    monkeypatch.setattr(routes.settings, "enable_amap_mcp", True)
    monkeypatch.setattr(routes, "tool_provider", AmapMcpAdapter(client=UnavailableClient()))

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["tools"]["mode"] == "amap_mcp"
    assert body["tools"]["amap_mcp_available"] is False
    assert "amap_mcp_unavailable" in body["config"]["warnings"]
