from app.agents.base import BaseAgent


class TransportAgent(BaseAgent):
    name = "transport"

    def __init__(self, tool_provider) -> None:
        self.tool_provider = tool_provider

    def can_handle(self, intent: str) -> bool:
        return intent == self.name

    async def process(self, request: dict, state: object) -> dict:
        options = await self.tool_provider.search_transport(request)
        return {"agent": self.name, "recommendations": options}

