import asyncio
import json

import pytest

from app.tools.agent_reach_adapter import AgentReachAdapter, AgentReachFetcher


@pytest.mark.asyncio
async def test_search_attraction_normalizes_fetcher_results():
    async def fetcher(operation: str, payload: dict):
        assert operation == "search_attraction"
        assert payload["destination"] == "杭州"
        return [
            {
                "title": "西湖",
                "snippet": "杭州经典湖景",
                "url": "https://example.com/west-lake",
                "source": "rss",
            }
        ]

    adapter = AgentReachAdapter(fetcher=fetcher)
    results = await adapter.search_attraction({"destination": "杭州"})

    assert results == [
        {
            "name": "西湖",
            "summary": "杭州经典湖景",
            "url": "https://example.com/west-lake",
            "source": "rss",
        }
    ]


@pytest.mark.asyncio
async def test_rag_search_normalizes_fetcher_results():
    async def fetcher(operation: str, payload: dict):
        assert operation == "rag_search"
        assert payload["query"] == "杭州西湖"
        return {
            "results": [
                {
                    "headline": "西湖游览建议",
                    "content": "适合半日游。",
                    "link": "https://example.com/west-lake-guide",
                    "source": "web",
                }
            ]
        }

    adapter = AgentReachAdapter(fetcher=fetcher)
    results = await adapter.rag_search("杭州西湖")

    assert results == [
        {
            "title": "西湖游览建议",
            "content": "适合半日游。",
            "url": "https://example.com/west-lake-guide",
            "source": "web",
        }
    ]


@pytest.mark.asyncio
async def test_search_attraction_falls_back_to_mock_on_fetcher_error():
    async def fetcher(operation: str, payload: dict):
        raise RuntimeError("boom")

    adapter = AgentReachAdapter(fetcher=fetcher)
    results = await adapter.search_attraction({"destination": "杭州"})

    assert results == [
        {"name": "杭州西湖", "duration_hours": 3},
        {"name": "杭州灵隐寺", "duration_hours": 2.5},
        {"name": "杭州河坊街", "duration_hours": 2},
    ]


@pytest.mark.asyncio
async def test_search_attraction_falls_back_to_mock_on_timeout():
    async def fetcher(operation: str, payload: dict):
        await asyncio.sleep(0.05)
        return []

    adapter = AgentReachAdapter(fetcher=fetcher, timeout_seconds=0.01)
    results = await adapter.search_attraction({"destination": "杭州"})

    assert results == [
        {"name": "杭州西湖", "duration_hours": 3},
        {"name": "杭州灵隐寺", "duration_hours": 2.5},
        {"name": "杭州河坊街", "duration_hours": 2},
    ]


@pytest.mark.asyncio
async def test_default_fetcher_uses_runner_and_parses_json_results():
    calls = []

    async def runner(command: list[str], timeout_seconds: float) -> str:
        calls.append((command, timeout_seconds))
        return json.dumps(
            {
                "results": [
                    {
                        "title": "West Lake travel guide",
                        "url": "https://example.com",
                        "snippet": "Classic Hangzhou route",
                    }
                ]
            }
        )

    fetcher = AgentReachFetcher(
        config={"search": {"num_results": 3}},
        timeout_seconds=5,
        runner=runner,
    )

    results = await fetcher(operation="rag_search", payload={"query": "Hangzhou West Lake"})

    assert results == [
        {
            "title": "West Lake travel guide",
            "url": "https://example.com",
            "snippet": "Classic Hangzhou route",
        }
    ]
    assert calls
    command, timeout_seconds = calls[0]
    assert command[:2] == ["mcporter", "call"]
    assert "exa.web_search_exa" in command[2]
    assert "Hangzhou West Lake" in command[2]
    assert "numResults: 3" in command[2]
    assert timeout_seconds == 5


def test_default_fetcher_reports_cli_availability(monkeypatch):
    monkeypatch.setattr("app.tools.agent_reach_adapter.shutil.which", lambda command: None)

    fetcher = AgentReachFetcher()

    assert fetcher.is_available() is False
