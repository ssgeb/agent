from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def can_handle(self, intent: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def process(self, request: dict, state: object) -> dict:
        raise NotImplementedError

