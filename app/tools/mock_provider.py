from app.tools.interface import ToolInterface


class MockProvider(ToolInterface):
    async def search_transport(self, params: dict) -> list[dict]:
        # 提供固定候选，便于在无外部依赖时稳定回归测试。
        origin = params.get("origin", "上海")
        destination = params.get("destination", "杭州")
        return [
            {"mode": "train", "from": origin, "to": destination, "price": 230, "duration_hours": 1.3},
            {"mode": "bus", "from": origin, "to": destination, "price": 120, "duration_hours": 2.8},
            {"mode": "flight", "from": origin, "to": destination, "price": 680, "duration_hours": 1.0},
        ]

    async def search_hotel(self, params: dict) -> list[dict]:
        city = params.get("destination", "杭州")
        return [
            {"name": f"{city}西湖景观酒店", "price_per_night": 680, "rating": 4.8},
            {"name": f"{city}中心商务酒店", "price_per_night": 420, "rating": 4.6},
        ]

    async def search_attraction(self, params: dict) -> list[dict]:
        city = params.get("destination", "杭州")
        return [
            {"name": f"{city}西湖", "duration_hours": 3},
            {"name": f"{city}灵隐寺", "duration_hours": 2.5},
            {"name": f"{city}河坊街", "duration_hours": 2},
        ]

    async def rag_search(self, query: str) -> list[dict]:
        return [{"source": "mock-knowledge", "content": f"RAG结果: {query}"}]
