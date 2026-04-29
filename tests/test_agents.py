import pytest

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.state import StateManager
from app.tools import MockProvider


@pytest.mark.asyncio
async def test_planner_routes_transport_intent():
    state_manager = StateManager()
    state_manager.create_session("s-100")
    provider = MockProvider()
    planner = PlannerAgent(
        state_manager=state_manager,
        agents=[TransportAgent(provider), HotelAgent(provider), ItineraryAgent(provider)],
    )

    result = await planner.process(
        "帮我查从上海到杭州的交通",
        state_manager.get_conversation_state("s-100"),
    )

    assert result["intent"] == "transport"
    assert len(result["recommendations"]) > 0
