from __future__ import annotations

from abc import ABC, abstractmethod


class ToolInterface(ABC):
    @abstractmethod
    async def search_transport(self, params: dict) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def search_hotel(self, params: dict) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def search_attraction(self, params: dict) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def rag_search(self, query: str) -> list[dict]:
        raise NotImplementedError

