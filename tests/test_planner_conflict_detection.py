import pytest

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.state import StateManager
from app.tools import MockProvider


def planner_factory(state_manager: StateManager) -> PlannerAgent:
    provider = MockProvider()
    return PlannerAgent(
        state_manager=state_manager,
        agents=[TransportAgent(provider), HotelAgent(provider), ItineraryAgent(provider)],
    )


@pytest.mark.asyncio
async def test_budget_conflict_triggers_pending_questions():
    state_manager = StateManager()
    state_manager.create_session("s-budget")
    state_manager.update_trip_state(
        "s-budget",
        {
            "origin": "上海",
            "destination": "杭州",
            "duration_days": 2,
            "budget": {"max": 100},
        },
    )
    planner = planner_factory(state_manager)

    result = await planner.process(
        "请帮我规划这次旅行",
        state_manager.get_conversation_state("s-budget"),
    )

    assert result["pending_questions"]
    assert any("预算" in question for question in result["pending_questions"])
    assert "budget" in result["conflicts"]


@pytest.mark.asyncio
async def test_origin_destination_conflict_triggers_pending_questions():
    state_manager = StateManager()
    state_manager.create_session("s-transport")
    state_manager.update_trip_state(
        "s-transport",
        {
            "origin": "上海",
            "destination": "上海",
            "duration_days": 2,
            "budget": {"max": 5000},
        },
    )
    planner = planner_factory(state_manager)

    result = await planner.process(
        "请帮我规划这次旅行",
        state_manager.get_conversation_state("s-transport"),
    )

    assert result["pending_questions"]
    assert any("出发地" in question or "目的地" in question for question in result["pending_questions"])
    assert "transport" in result["conflicts"]


@pytest.mark.asyncio
async def test_no_conflict_leaves_pending_questions_and_conflicts_empty():
    state_manager = StateManager()
    state_manager.create_session("s-clear")
    state_manager.update_trip_state(
        "s-clear",
        {
            "origin": "上海",
            "destination": "杭州",
            "duration_days": 2,
            "budget": {"max": 5000},
        },
    )
    planner = planner_factory(state_manager)

    result = await planner.process(
        "请帮我规划这次旅行",
        state_manager.get_conversation_state("s-clear"),
    )

    assert result["pending_questions"] == []
    assert result["conflicts"] == []
