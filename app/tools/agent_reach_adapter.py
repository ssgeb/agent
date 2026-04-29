from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from typing import Any

from app.tools.interface import ToolInterface
from app.tools.mock_provider import MockProvider


AgentReachRunner = Callable[[list[str], float], Awaitable[str]]


async def _subprocess_runner(command: list[str], timeout_seconds: float) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    if process.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", errors="replace").strip() or "agent-reach command failed")
    return stdout.decode("utf-8", errors="replace")


class AgentReachFetcher:
    """Read-only Agent-Reach fetcher backed by the configured search channel."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        timeout_seconds: float = 3.0,
        runner: AgentReachRunner | None = None,
    ) -> None:
        self.config = config or {}
        self.timeout_seconds = timeout_seconds
        self.runner = runner or _subprocess_runner

    async def __call__(self, operation: str, payload: dict) -> list[dict]:
        query = self._build_query(operation, payload)
        command = self._build_search_command(query)
        output = await self.runner(command, self.timeout_seconds)
        return self._parse_results(output)

    def _build_query(self, operation: str, payload: dict) -> str:
        if operation == "search_attraction":
            destination = str(payload.get("destination") or payload.get("city") or "")
            message = str(payload.get("message") or "")
            query = f"{destination} travel attractions {message}".strip()
            return query or "travel attractions"
        if operation == "rag_search":
            return str(payload.get("query") or "").strip()
        return "travel planning"

    def _build_search_command(self, query: str) -> list[str]:
        search_config = self.config.get("search", {}) if isinstance(self.config, dict) else {}
        num_results = int(search_config.get("num_results") or self.config.get("num_results") or 5)
        escaped_query = query.replace("\\", "\\\\").replace('"', '\\"')
        expression = f'exa.web_search_exa(query: "{escaped_query}", numResults: {num_results})'
        return ["mcporter", "call", expression]

    def is_available(self) -> bool:
        return shutil.which("mcporter") is not None

    def _parse_results(self, output: str) -> list[dict]:
        data = self._load_json(output)
        if isinstance(data, dict):
            for key in ("results", "items", "data"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
                if isinstance(value, dict):
                    nested = value.get("results") or value.get("items")
                    if isinstance(nested, list):
                        return [item for item in nested if isinstance(item, dict)]
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []

    def _load_json(self, output: str) -> Any:
        stripped = output.strip()
        if not stripped:
            return []
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            # Some CLI wrappers print a command echo or prose before JSON.
            start = min([idx for idx in (stripped.find("{"), stripped.find("[")) if idx >= 0], default=-1)
            if start < 0:
                return []
            return json.loads(stripped[start:])


class AgentReachAdapter(ToolInterface):
    def __init__(
        self,
        fetcher: Callable[[str, dict], Awaitable[Any]] | None = None,
        timeout_seconds: float = 3.0,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.fetcher = fetcher or AgentReachFetcher(config=config, timeout_seconds=timeout_seconds)
        self._mock = MockProvider()

    async def search_transport(self, params: dict) -> list[dict]:
        return await self._mock.search_transport(params)

    async def search_hotel(self, params: dict) -> list[dict]:
        return await self._mock.search_hotel(params)

    async def search_attraction(self, params: dict) -> list[dict]:
        fetched = await self._fetch_with_fallback("search_attraction", params)
        if fetched is not None:
            return [
                {
                    "name": item.get("name") or item.get("title") or item.get("headline") or "",
                    "summary": item.get("summary") or item.get("snippet") or item.get("content") or "",
                    "url": item.get("url") or item.get("link") or "",
                    "source": item.get("source") or "agent_reach",
                }
                for item in fetched
                if isinstance(item, dict)
            ]
        return await self._mock.search_attraction(params)

    async def rag_search(self, query: str) -> list[dict]:
        fetched = await self._fetch_with_fallback("rag_search", {"query": query})
        if fetched is not None:
            return [
                {
                    "title": item.get("title") or item.get("headline") or item.get("name") or "",
                    "content": item.get("content") or item.get("summary") or item.get("snippet") or "",
                    "url": item.get("url") or item.get("link") or "",
                    "source": item.get("source") or "agent_reach",
                }
                for item in fetched
                if isinstance(item, dict)
            ]
        return await self._mock.rag_search(query)

    async def _fetch_with_fallback(self, operation: str, payload: dict) -> list[dict] | None:
        if self.fetcher is None:
            return None
        try:
            result = await asyncio.wait_for(
                self.fetcher(operation=operation, payload=payload),
                timeout=self.timeout_seconds,
            )
        except (asyncio.TimeoutError, Exception):
            # 外部 fetcher 超时或失败时，直接降级到 MockProvider，保证工具层稳定可用。
            return None

        if isinstance(result, dict):
            results = result.get("results")
            if isinstance(results, list):
                return results
            return []
        if isinstance(result, list):
            return result
        return []

    def is_available(self) -> bool:
        availability_check = getattr(self.fetcher, "is_available", None)
        if availability_check is None:
            return True
        return bool(availability_check())
