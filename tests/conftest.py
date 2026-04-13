import pytest

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.services import ChatService, SessionService
from app.state import StateManager
from app.tools import MockProvider


@pytest.fixture
def tool_provider() -> MockProvider:
    return MockProvider()


@pytest.fixture
def state_manager() -> StateManager:
    return StateManager()


@pytest.fixture
def planner_agent(tool_provider: MockProvider, state_manager: StateManager) -> PlannerAgent:
    return PlannerAgent(
        state_manager=state_manager,
        agents=[TransportAgent(tool_provider), HotelAgent(tool_provider), ItineraryAgent(tool_provider)],
    )


@pytest.fixture
def chat_service(state_manager: StateManager, planner_agent: PlannerAgent) -> ChatService:
    return ChatService(state_manager=state_manager, planner_agent=planner_agent)


@pytest.fixture
def session_service(state_manager: StateManager) -> SessionService:
    return SessionService(state_manager=state_manager)
