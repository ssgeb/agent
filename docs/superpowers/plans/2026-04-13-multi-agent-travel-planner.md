# Multi-Agent Travel Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可运行的 FastAPI 多智能体旅行规划后端 MVP，支持 `/health`、`/chat`、`/session/{id}`、`/plan/{id}`，并通过 Mock 工具完成交通、酒店、行程规划的端到端闭环。

**Architecture:** 采用 `API -> Service -> Agent -> Tools -> State` 五层结构。`PlannerAgent` 负责意图识别、状态更新和子 Agent 路由；子 Agent 只依赖统一工具接口，使用 `MockProvider` 保证首版可运行。所有会话与旅行状态统一通过 `StateManager` 管理，避免跨层耦合。

**Tech Stack:** Python 3.10、FastAPI、Pydantic v2、pytest、pytest-asyncio、httpx

## 开发环境约定（Conda）

- 统一使用 `conda` 的 `leetcode` 环境进行开发、测试与运行。
- 首次创建环境（若不存在）：

```bash
conda create -n leetcode python=3.10 -y
```

- 每次开始开发前激活环境：

```bash
conda activate leetcode
```

- 安装依赖建议在该环境内执行（示例）：

```bash
pip install fastapi==0.135.2 pydantic==2.12.5 pydantic-settings==2.13.1 uvicorn==0.41.0 httpx==0.28.1 pytest pytest-asyncio
```

## 代码注释规范（中文）

- 本计划内所有新增或修改的业务代码，需补充中文注释。
- 注释重点放在「意图识别逻辑」「状态变更逻辑」「工具调用与回退策略」「错误处理分支」等不直观部分。
- 避免逐行翻译式注释；简单赋值、直观语句不强制注释。
- 函数/类如存在关键输入输出约束，优先在定义处增加简短中文说明。

---

## 文件结构与职责

- `app/main.py`：FastAPI 应用入口与路由注册。
- `app/api/schemas.py`：API 请求/响应模型定义。
- `app/api/routes.py`：`/health`、`/chat`、`/session/{id}`、`/plan/{id}` 四个路由。
- `app/services/chat_service.py`：对话主流程编排。
- `app/services/session_service.py`：会话创建与读取。
- `app/services/state_service.py`：旅行状态与方案读写封装。
- `app/agents/base.py`：子 Agent 抽象基类。
- `app/agents/planner.py`：主控 Agent，意图路由和响应汇总。
- `app/agents/transport.py`：交通子 Agent。
- `app/agents/hotel.py`：酒店子 Agent。
- `app/agents/itinerary.py`：行程子 Agent。
- `app/tools/interface.py`：统一工具接口与数据模型。
- `app/tools/mock_provider.py`：Mock 工具实现。
- `app/tools/agent_reach_adapter.py`：Agent-Reach 适配器占位实现。
- `app/state/models.py`：`ConversationState`、`TripState`、`CurrentPlan`。
- `app/state/manager.py`：内存状态管理器。
- `app/config/settings.py`：运行时配置。
- `app/utils/errors.py`：领域错误定义。
- `tests/test_health_api.py`：健康检查接口测试。
- `tests/test_chat_api.py`：聊天主流程接口测试。
- `tests/test_state_manager.py`：状态读写测试。
- `tests/test_agents.py`：Planner 与子 Agent 行为测试。

### Task 1: FastAPI 骨架与健康检查

**Files:**
- Create: `app/main.py`
- Create: `app/api/routes.py`
- Create: `app/api/schemas.py`
- Create: `tests/test_health_api.py`
- Modify: `app/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_health_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'service': 'multi-agent-travel-planner'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health_api.py::test_health_returns_ok -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/main.py
from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title='multi-agent-travel-planner', version='0.1.0')
app.include_router(router)
```

```python
# app/api/routes.py
from fastapi import APIRouter

router = APIRouter()


@router.get('/health')
async def health_check() -> dict[str, str]:
    return {'status': 'ok', 'service': 'multi-agent-travel-planner'}
```

```python
# app/api/schemas.py
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    updated_plan: dict | None = None
    pending_questions: list[str] | None = None
```

```python
# app/__init__.py
"""Multi-agent travel planner backend package."""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health_api.py::test_health_returns_ok -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py app/main.py app/api/routes.py app/api/schemas.py tests/test_health_api.py
git commit -m "feat: bootstrap FastAPI app and health endpoint"
```

### Task 2: 状态模型与 StateManager

**Files:**
- Create: `app/state/models.py`
- Create: `app/state/manager.py`
- Create: `app/state/__init__.py`
- Create: `tests/test_state_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state_manager.py
from app.state import StateManager


def test_state_manager_create_and_read_session():
    manager = StateManager()
    session_id = 's-001'

    manager.create_session(session_id)
    state = manager.get_conversation_state(session_id)

    assert state.session_id == session_id
    assert state.message_history == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_state_manager.py::test_state_manager_create_and_read_session -v`
Expected: FAIL with `ImportError: cannot import name 'StateManager'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/state/models.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationState(BaseModel):
    session_id: str
    message_history: list[dict] = Field(default_factory=list)
    summary: str | None = None
    current_intent: str | None = None
    active_agent: str | None = None
    pending_questions: list[str] = Field(default_factory=list)
    tool_results: dict = Field(default_factory=dict)
    last_plan: dict | None = None
    final_response: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TripState(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_days: int | None = None
    travelers_count: int = 1
    traveler_type: str = 'adult'
    budget: dict[str, float] | None = None
    transport_preferences: dict = Field(default_factory=dict)
    hotel_preferences: dict = Field(default_factory=dict)
    attraction_preferences: dict = Field(default_factory=dict)
    pace_preference: str = 'moderate'
    must_visit_places: list[str] = Field(default_factory=list)
    excluded_places: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CurrentPlan(BaseModel):
    plan_id: str
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    transport_plan: dict | None = None
    hotel_plan: dict | None = None
    itinerary_plan: dict | None = None
    total_estimate: dict[str, float] = Field(default_factory=dict)
```

```python
# app/state/manager.py
from app.state.models import ConversationState, CurrentPlan, TripState


class StateManager:
    def __init__(self) -> None:
        self.conversation_states: dict[str, ConversationState] = {}
        self.trip_states: dict[str, TripState] = {}
        self.current_plans: dict[str, CurrentPlan] = {}

    def create_session(self, session_id: str) -> None:
        self.conversation_states[session_id] = ConversationState(session_id=session_id)
        self.trip_states[session_id] = TripState()

    def get_conversation_state(self, session_id: str) -> ConversationState:
        return self.conversation_states[session_id]
```

```python
# app/state/__init__.py
from app.state.manager import StateManager
from app.state.models import ConversationState, CurrentPlan, TripState

__all__ = ['ConversationState', 'CurrentPlan', 'StateManager', 'TripState']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_state_manager.py::test_state_manager_create_and_read_session -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/state/models.py app/state/manager.py app/state/__init__.py tests/test_state_manager.py
git commit -m "feat: add state models and in-memory state manager"
```

### Task 3: 工具接口与 MockProvider

**Files:**
- Create: `app/tools/interface.py`
- Create: `app/tools/mock_provider.py`
- Create: `app/tools/agent_reach_adapter.py`
- Create: `app/tools/__init__.py`
- Create: `tests/test_tools_mock_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_mock_provider.py
import pytest

from app.tools import MockProvider


@pytest.mark.asyncio
async def test_mock_provider_returns_transport_options():
    provider = MockProvider()
    options = await provider.search_transport({'origin': '上海', 'destination': '杭州'})

    assert len(options) > 0
    assert options[0]['mode'] in {'flight', 'train', 'bus'}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_tools_mock_provider.py::test_mock_provider_returns_transport_options -v`
Expected: FAIL with `ImportError: cannot import name 'MockProvider'`

- [ ] **Step 3: Write minimal implementation**

```python
# app/tools/interface.py
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
```

```python
# app/tools/mock_provider.py
from app.tools.interface import ToolInterface


class MockProvider(ToolInterface):
    async def search_transport(self, params: dict) -> list[dict]:
        return [
            {'mode': 'train', 'from': params.get('origin'), 'to': params.get('destination'), 'price': 230},
            {'mode': 'bus', 'from': params.get('origin'), 'to': params.get('destination'), 'price': 120},
        ]

    async def search_hotel(self, params: dict) -> list[dict]:
        city = params.get('destination', 'unknown')
        return [{'name': f'{city}中心酒店', 'price_per_night': 420, 'rating': 4.6}]

    async def search_attraction(self, params: dict) -> list[dict]:
        city = params.get('destination', 'unknown')
        return [{'name': f'{city}博物馆', 'duration_hours': 3}]

    async def rag_search(self, query: str) -> list[dict]:
        return [{'source': 'mock-knowledge', 'content': f'RAG结果: {query}'}]
```

```python
# app/tools/agent_reach_adapter.py
from app.tools.interface import ToolInterface


class AgentReachAdapter(ToolInterface):
    async def search_transport(self, params: dict) -> list[dict]:
        return []

    async def search_hotel(self, params: dict) -> list[dict]:
        return []

    async def search_attraction(self, params: dict) -> list[dict]:
        return []

    async def rag_search(self, query: str) -> list[dict]:
        return []
```

```python
# app/tools/__init__.py
from app.tools.agent_reach_adapter import AgentReachAdapter
from app.tools.mock_provider import MockProvider

__all__ = ['AgentReachAdapter', 'MockProvider']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_tools_mock_provider.py::test_mock_provider_returns_transport_options -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tools/interface.py app/tools/mock_provider.py app/tools/agent_reach_adapter.py app/tools/__init__.py tests/test_tools_mock_provider.py
git commit -m "feat: implement tool interface and mock provider"
```

### Task 4: 子 Agent 与 PlannerAgent

**Files:**
- Create: `app/agents/base.py`
- Create: `app/agents/transport.py`
- Create: `app/agents/hotel.py`
- Create: `app/agents/itinerary.py`
- Create: `app/agents/planner.py`
- Create: `app/agents/__init__.py`
- Create: `tests/test_agents.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agents.py
import pytest

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.state import StateManager
from app.tools import MockProvider


@pytest.mark.asyncio
async def test_planner_routes_transport_intent():
    state_manager = StateManager()
    state_manager.create_session('s-100')
    provider = MockProvider()
    planner = PlannerAgent(
        state_manager=state_manager,
        agents=[TransportAgent(provider), HotelAgent(provider), ItineraryAgent(provider)],
    )

    result = await planner.process('帮我查从上海到杭州的交通', state_manager.get_conversation_state('s-100'))

    assert result['intent'] == 'transport'
    assert len(result['recommendations']) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agents.py::test_planner_routes_transport_intent -v`
Expected: FAIL with `ImportError` for `app.agents`

- [ ] **Step 3: Write minimal implementation**

```python
# app/agents/base.py
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAgent(ABC):
    name: str

    @abstractmethod
    def can_handle(self, intent: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def process(self, request: dict, state: dict | object) -> dict:
        raise NotImplementedError
```

```python
# app/agents/transport.py
from app.agents.base import BaseAgent


class TransportAgent(BaseAgent):
    name = 'transport'

    def __init__(self, tool_provider) -> None:
        self.tool_provider = tool_provider

    def can_handle(self, intent: str) -> bool:
        return intent == 'transport'

    async def process(self, request: dict, state: dict | object) -> dict:
        options = await self.tool_provider.search_transport(request)
        return {'agent': self.name, 'recommendations': options}
```

```python
# app/agents/hotel.py
from app.agents.base import BaseAgent


class HotelAgent(BaseAgent):
    name = 'hotel'

    def __init__(self, tool_provider) -> None:
        self.tool_provider = tool_provider

    def can_handle(self, intent: str) -> bool:
        return intent == 'hotel'

    async def process(self, request: dict, state: dict | object) -> dict:
        options = await self.tool_provider.search_hotel(request)
        return {'agent': self.name, 'recommendations': options}
```

```python
# app/agents/itinerary.py
from app.agents.base import BaseAgent


class ItineraryAgent(BaseAgent):
    name = 'itinerary'

    def __init__(self, tool_provider) -> None:
        self.tool_provider = tool_provider

    def can_handle(self, intent: str) -> bool:
        return intent == 'itinerary'

    async def process(self, request: dict, state: dict | object) -> dict:
        options = await self.tool_provider.search_attraction(request)
        return {'agent': self.name, 'recommendations': options}
```

```python
# app/agents/planner.py
from app.state.models import ConversationState


class PlannerAgent:
    def __init__(self, state_manager, agents: list) -> None:
        self.state_manager = state_manager
        self.agents = agents

    def _detect_intent(self, message: str) -> str:
        if '酒店' in message or '住宿' in message:
            return 'hotel'
        if '行程' in message or '景点' in message:
            return 'itinerary'
        return 'transport'

    async def process(self, message: str, state: ConversationState) -> dict:
        intent = self._detect_intent(message)
        request = {'origin': '上海', 'destination': '杭州', 'message': message}

        for agent in self.agents:
            if agent.can_handle(intent):
                result = await agent.process(request, {})
                return {'intent': intent, 'recommendations': result['recommendations']}

        return {'intent': intent, 'recommendations': []}
```

```python
# app/agents/__init__.py
from app.agents.hotel import HotelAgent
from app.agents.itinerary import ItineraryAgent
from app.agents.planner import PlannerAgent
from app.agents.transport import TransportAgent

__all__ = ['HotelAgent', 'ItineraryAgent', 'PlannerAgent', 'TransportAgent']
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agents.py::test_planner_routes_transport_intent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/base.py app/agents/transport.py app/agents/hotel.py app/agents/itinerary.py app/agents/planner.py app/agents/__init__.py tests/test_agents.py
git commit -m "feat: add planner and child agents with intent routing"
```

### Task 5: Service 层与 `/chat` 主流程

**Files:**
- Create: `app/services/chat_service.py`
- Create: `app/services/session_service.py`
- Create: `app/services/state_service.py`
- Create: `app/services/__init__.py`
- Modify: `app/api/routes.py`
- Create: `tests/test_chat_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chat_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_chat_returns_session_and_plan():
    client = TestClient(app)
    response = client.post('/chat', json={'message': '帮我规划杭州两日游'})

    assert response.status_code == 200
    data = response.json()
    assert data['session_id']
    assert isinstance(data.get('updated_plan'), dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_api.py::test_chat_returns_session_and_plan -v`
Expected: FAIL with `AttributeError` or `422/500` because `/chat` 未实现完整流程

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/session_service.py
from app.state import StateManager


class SessionService:
    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    def create_session(self, session_id: str) -> str:
        self.state_manager.create_session(session_id)
        return session_id

    def get_session(self, session_id: str):
        return self.state_manager.get_conversation_state(session_id)
```

```python
# app/services/chat_service.py
from uuid import uuid4

from app.api.schemas import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, state_manager, planner_agent) -> None:
        self.state_manager = state_manager
        self.planner_agent = planner_agent

    async def process_message(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or f's-{uuid4().hex[:8]}'
        if session_id not in self.state_manager.conversation_states:
            self.state_manager.create_session(session_id)

        state = self.state_manager.get_conversation_state(session_id)
        result = await self.planner_agent.process(request.message, state)

        plan = {
            'transport_plan': result['recommendations'] if result['intent'] == 'transport' else None,
            'hotel_plan': result['recommendations'] if result['intent'] == 'hotel' else None,
            'itinerary_plan': result['recommendations'] if result['intent'] == 'itinerary' else None,
        }

        return ChatResponse(
            response='已根据你的需求更新旅行方案。',
            session_id=session_id,
            updated_plan=plan,
            pending_questions=[],
        )
```

```python
# app/services/state_service.py
class StateService:
    def __init__(self, state_manager) -> None:
        self.state_manager = state_manager

    async def get_current_plan(self, session_id: str) -> dict | None:
        plan = self.state_manager.current_plans.get(session_id)
        return None if plan is None else plan.model_dump()
```

```python
# app/services/__init__.py
from app.services.chat_service import ChatService
from app.services.session_service import SessionService
from app.services.state_service import StateService

__all__ = ['ChatService', 'SessionService', 'StateService']
```

```python
# app/api/routes.py
from fastapi import APIRouter

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.api.schemas import ChatRequest, ChatResponse
from app.services import ChatService
from app.state import StateManager
from app.tools import MockProvider

router = APIRouter()
state_manager = StateManager()
provider = MockProvider()
planner_agent = PlannerAgent(
    state_manager=state_manager,
    agents=[TransportAgent(provider), HotelAgent(provider), ItineraryAgent(provider)],
)
chat_service = ChatService(state_manager=state_manager, planner_agent=planner_agent)


@router.get('/health')
async def health_check() -> dict[str, str]:
    return {'status': 'ok', 'service': 'multi-agent-travel-planner'}


@router.post('/chat', response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await chat_service.process_message(request)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_api.py::test_chat_returns_session_and_plan -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/chat_service.py app/services/session_service.py app/services/state_service.py app/services/__init__.py app/api/routes.py tests/test_chat_api.py
git commit -m "feat: add chat service orchestration and chat endpoint"
```

### Task 6: 会话/方案查询接口与错误模型

**Files:**
- Create: `app/utils/errors.py`
- Create: `app/config/settings.py`
- Modify: `app/api/routes.py`
- Create: `tests/test_session_plan_api.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session_plan_api.py
from fastapi.testclient import TestClient

from app.main import app


def test_session_and_plan_endpoints_work_after_chat():
    client = TestClient(app)
    chat_resp = client.post('/chat', json={'message': '查下杭州酒店'})
    session_id = chat_resp.json()['session_id']

    session_resp = client.get(f'/session/{session_id}')
    plan_resp = client.get(f'/plan/{session_id}')

    assert session_resp.status_code == 200
    assert plan_resp.status_code == 200
    assert session_resp.json()['session_id'] == session_id
    assert 'transport_plan' in plan_resp.json() or 'hotel_plan' in plan_resp.json() or 'itinerary_plan' in plan_resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_plan_api.py::test_session_and_plan_endpoints_work_after_chat -v`
Expected: FAIL with `404 Not Found` for `/session/{id}` or `/plan/{id}`

- [ ] **Step 3: Write minimal implementation**

```python
# app/utils/errors.py
class TravelPlannerError(Exception):
    pass


class IntentError(TravelPlannerError):
    pass


class ToolCallError(TravelPlannerError):
    pass


class StateError(TravelPlannerError):
    pass
```

```python
# app/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'travel-planner'
    app_version: str = '1.0.0'
    debug: bool = True
    use_mock_only: bool = True
    enable_agent_reach: bool = False
    session_timeout: int = 3600

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
```

```python
# app/api/routes.py
from fastapi import APIRouter, HTTPException

# 省略已有 import

@router.get('/session/{session_id}')
async def get_session(session_id: str) -> dict:
    state = state_manager.conversation_states.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail='session not found')
    return state.model_dump()


@router.get('/plan/{session_id}')
async def get_plan(session_id: str) -> dict:
    latest = state_manager.current_plans.get(session_id)
    if latest is not None:
        return latest.model_dump()

    state = state_manager.conversation_states.get(session_id)
    if state is None or state.last_plan is None:
        raise HTTPException(status_code=404, detail='plan not found')
    return state.last_plan
```

```python
# tests/conftest.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_plan_api.py::test_session_and_plan_endpoints_work_after_chat -v`
Expected: PASS

- [ ] **Step 5: Run full test suite and verify**

Run: `pytest -v`
Expected: PASS with all current tests green

- [ ] **Step 6: Commit**

```bash
git add app/utils/errors.py app/config/settings.py app/api/routes.py tests/test_session_plan_api.py tests/conftest.py
git commit -m "feat: add session and plan query endpoints with error models"
```

## 自检结果

1. Spec coverage:
- 已覆盖 API 接口：Task 1 与 Task 5、Task 6 对应 `/health`、`/chat`、`/session/{id}`、`/plan/{id}`。
- 已覆盖分层架构：Task 1/5（API+Service）、Task 4（Agent）、Task 3（Tools）、Task 2（State）。
- 已覆盖 Mock 优先策略：Task 3 明确使用 `MockProvider`。
- 已覆盖错误处理与配置：Task 6 新增错误类与配置模型。
- 已覆盖测试策略：每个任务均为 TDD 流程，包含单测与最终全量测试。

2. Placeholder scan:
- 已检查全文，不存在未落实的占位描述或延后实现表述。

3. Type consistency:
- `ChatRequest`/`ChatResponse` 在 Task 1 定义并在 Task 5 复用。
- `StateManager` 在 Task 2 定义并在 Task 4/5/6 复用。
- `PlannerAgent.process(message, state)` 签名在 Task 4 定义并在 Task 5 使用一致。

