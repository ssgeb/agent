from __future__ import annotations

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.api.schemas import (
    BookingListResponse,
    BookingRecordResponse,
    CreateBookingRequest,
    ChatRequest,
    ChatResponse,
    RevisePlanRequest,
    RevisePlanResponse,
    UserPreferences,
    UserPreferencesResponse,
)
from app.config.settings import Settings
from app.db import TaskRepository
from app.orchestration.stategraph_runner import StateGraphRunner
from app.queue.redis_queue import RedisQueue
from app.services import ChatService, PlanRevisionService, TaskService
from app.services.auth_service import AuthError
from app.state import StateManager
from app.tools import AgentReachAdapter, AmapMcpAdapter, MockProvider, create_tool_provider
from app.utils.error_codes import INTERNAL_ERROR, PLAN_NOT_FOUND, SESSION_NOT_FOUND, build_error
from app.utils.errors import StateError
from app.workers.task_worker import TaskWorker

router = APIRouter()

settings = Settings()
task_repository = TaskRepository(settings.resolved_database_url)
state_manager = StateManager(repository=task_repository)
tool_provider = create_tool_provider(settings)
planner_agent = PlannerAgent(
    state_manager=state_manager,
    agents=[
        TransportAgent(tool_provider),
        HotelAgent(tool_provider),
        ItineraryAgent(tool_provider),
    ],
)
chat_service = ChatService(state_manager=state_manager, planner_agent=planner_agent)
plan_revision_service = PlanRevisionService(state_manager=state_manager, planner_agent=planner_agent)

# V3: 任务持久化与异步执行组件。
task_queue = RedisQueue(
    redis_url=settings.redis_url or None,
    idempotency_key_ttl_seconds=settings.idempotency_key_ttl_seconds,
)
task_service = TaskService(repository=task_repository, queue=task_queue)
stategraph_runner = StateGraphRunner(chat_service=chat_service)
task_worker = TaskWorker(
    repository=task_repository,
    runner=stategraph_runner,
    queue=task_queue,
    max_retries=settings.max_task_retries,
    session_lock_ttl_seconds=settings.session_lock_ttl_seconds,
)

session_owner_ids: dict[str, str] = {}
PREFERENCE_KEYS = {
    "budget",
    "transport_preferences",
    "hotel_preferences",
    "attraction_preferences",
    "pace_preference",
    "must_visit_places",
    "excluded_places",
    "notes",
}


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _auth_context(request: Request) -> tuple[bool, str | None, bool]:
    authorization = request.headers.get("authorization")
    if not authorization:
        return False, None, False

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return True, None, True

    try:
        from app.api.auth import auth_service

        user = auth_service.get_current_user(token)
    except AuthError:
        return True, None, True
    return True, user["user_id"], False


def _json_error(status_code: int, code: str, message: str, request: Request) -> JSONResponse:
    body = build_error(code, message, request_id=_request_id(request))
    return JSONResponse(status_code=status_code, content=body)


def _serialize_plan_snapshots(snapshots):
    return [
        {
            "plan_id": snap.plan_id,
            "task_id": snap.task_id,
            "version": snap.version,
            "plan": snap.plan_json,
            "created_at": snap.created_at.isoformat(),
        }
        for snap in snapshots
    ]


def _serialize_session_state(state):
    conversation = state.conversation_state_json or {}
    history = conversation.get("message_history") or []
    last_user_message = next(
        (
            item.get("content")
            for item in reversed(history)
            if isinstance(item, dict) and item.get("role") == "user"
        ),
        "",
    )
    last_plan = conversation.get("last_plan") or {}
    title = conversation.get("summary") or last_plan.get("overview") or last_user_message or state.session_id
    preview = last_plan.get("overview") or last_user_message or title
    return {
        "session_id": state.session_id,
        "title": title,
        "preview": preview,
        "updated_at": state.updated_at.isoformat(),
    }


def _serialize_booking_record(record) -> dict:
    return {
        "booking_id": record.booking_id,
        "user_id": record.user_id,
        "session_id": record.session_id,
        "booking_type": record.booking_type,
        "item_name": record.item_name,
        "amount": record.amount,
        "currency": record.currency,
        "status": record.status,
        "payload": dict(record.payload_json or {}),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _normalize_preferences(preferences: dict | UserPreferences | None = None) -> UserPreferences:
    if isinstance(preferences, UserPreferences):
        return preferences
    return UserPreferences.model_validate(preferences or {})


def _preferences_for_trip_state(preferences: dict | UserPreferences | None) -> dict[str, object]:
    data = _normalize_preferences(preferences).model_dump()
    return {key: value for key, value in data.items() if value not in (None, {}, [])}


def _apply_user_preferences_to_session(session_id: str, user_id: str) -> None:
    preferences = task_repository.get_user_preferences(user_id)
    updates = _preferences_for_trip_state(preferences)
    if updates:
        state_manager.update_trip_state(session_id, updates)


def _remember_preference_updates(user_id: str, updates: dict[str, object]) -> None:
    preference_updates = {key: updates[key] for key in PREFERENCE_KEYS if key in updates}
    if not preference_updates:
        return
    current = _normalize_preferences(task_repository.get_user_preferences(user_id)).model_dump()
    current.update(preference_updates)
    task_repository.upsert_user_preferences(user_id, _normalize_preferences(current).model_dump())


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "multi-agent-travel-planner"}


@router.get("/health/ready")
async def readiness_check() -> dict:
    database_available = True
    try:
        with task_repository.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_available = False

    queue_mode = "redis" if getattr(task_queue, "_redis", None) is not None else "local"
    if isinstance(tool_provider, AmapMcpAdapter):
        tool_mode = "amap_mcp"
    elif isinstance(tool_provider, AgentReachAdapter):
        tool_mode = "agent_reach"
    else:
        tool_mode = "mock"

    agent_reach_available = True
    if isinstance(tool_provider, AgentReachAdapter):
        agent_reach_available = tool_provider.is_available()
    amap_mcp_available = True
    if isinstance(tool_provider, AmapMcpAdapter):
        amap_mcp_available = tool_provider.is_available()

    tools_degraded = (
        settings.enable_agent_reach
        and isinstance(tool_provider, AgentReachAdapter)
        and not agent_reach_available
    ) or (
        settings.enable_amap_mcp
        and isinstance(tool_provider, AmapMcpAdapter)
        and not amap_mcp_available
    ) or (
        (settings.enable_agent_reach or settings.enable_amap_mcp) and isinstance(tool_provider, MockProvider)
    )

    config_warnings: list[str] = []
    if settings.resolved_database_url.startswith("sqlite"):
        config_warnings.append("sqlite_database")
    if queue_mode == "local":
        config_warnings.append("local_queue")
    if tools_degraded:
        config_warnings.append("agent_reach_fallback_to_mock")
    if isinstance(tool_provider, AgentReachAdapter) and not agent_reach_available:
        config_warnings.append("agent_reach_cli_unavailable")
    if isinstance(tool_provider, AmapMcpAdapter) and not amap_mcp_available:
        config_warnings.append("amap_mcp_unavailable")
    if settings.use_mock_only:
        config_warnings.append("mock_only")

    status = "ready" if database_available and not tools_degraded else "degraded"
    return {
        "status": status,
        "database": {
            "available": database_available,
            "driver": settings.db_driver,
        },
        "queue": {
            "mode": queue_mode,
            "available": True,
        },
        "tools": {
            "mode": tool_mode,
            "amap_mcp_enabled": settings.enable_amap_mcp,
            "amap_mcp_available": amap_mcp_available,
            "agent_reach_enabled": settings.enable_agent_reach,
            "agent_reach_available": agent_reach_available,
            "degraded": tools_degraded,
        },
        "config": {
            "warnings": config_warnings,
        },
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | JSONResponse:
    _, user_id, invalid_auth = _auth_context(http_request)
    if invalid_auth:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", http_request)

    if user_id is not None:
        session_id = request.session_id or f"s-{uuid4().hex[:8]}"
        is_new_session = session_id not in state_manager.conversation_states
        if is_new_session:
            state_manager.create_session(session_id)
            _apply_user_preferences_to_session(session_id, user_id)
        request = ChatRequest(message=request.message, session_id=session_id)

    response = await chat_service.process_message(request)
    if user_id is not None:
        session_owner_ids[response.session_id] = user_id
    return response


@router.post("/chat/async", status_code=202, response_model=None)
async def chat_async(chat_request: ChatRequest, http_request: Request):
    # 异步任务入口：只创建任务并入队，不阻塞等待 Agent 全流程完成。
    _, user_id, invalid_auth = _auth_context(http_request)
    if invalid_auth:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", http_request)
    session_id = chat_request.session_id or f"s-{uuid4().hex[:8]}"
    is_new_session = session_id not in state_manager.conversation_states
    if is_new_session:
        state_manager.create_session(session_id)
        if user_id is not None:
            _apply_user_preferences_to_session(session_id, user_id)
    if user_id is not None:
        session_owner_ids[session_id] = user_id
    return task_service.create_chat_task(
        session_id=session_id,
        message=chat_request.message,
        request_id=_request_id(http_request),
        user_id=user_id,
    )


@router.post("/tasks/consume-once", response_model=None)
async def consume_one_task():
    # 手动触发一次队列消费，便于本地调试与最小闭环验证。
    payload = task_queue.dequeue()
    if payload is None:
        return {"consumed": False, "processed": False, "task_id": None}

    # 在异步路由中转到线程执行，避免与当前事件循环冲突。
    processed = await asyncio.to_thread(task_worker.process_one, payload)
    return {
        "consumed": True,
        "processed": bool(processed),
        "task_id": payload.get("task_id"),
    }


@router.post("/tasks/consume-batch", response_model=None)
async def consume_batch_tasks(max_tasks: int = 10, blocking_timeout_seconds: float = 0.05):
    """批量消费任务，便于本地快速压测多会话并发场景。"""
    consumed = await asyncio.to_thread(
        task_worker.run_loop,
        max_iterations=max(max_tasks, 0),
        blocking_timeout_seconds=max(blocking_timeout_seconds, 0.0),
    )
    return {"consumed_count": consumed}


@router.post("/tasks/recover", response_model=None)
async def recover_tasks():
    """触发恢复逻辑：只回放超时未推进的任务，避免重复执行健康 RUNNING 任务。"""
    recovered = await asyncio.to_thread(
        task_worker.resume_incomplete_tasks,
        stale_seconds=settings.task_recovery_stale_seconds,
    )
    return {"recovered_task_ids": recovered, "recovered_count": len(recovered)}


@router.get("/task/{task_id}", response_model=None)
async def get_task(task_id: str, request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)
    try:
        task = task_service.get_task_for_user(task_id, user_id)
    except KeyError:
        return _json_error(404, "TASK_NOT_FOUND", "task not found", request)
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "status": task.status,
        "error_code": task.error_code,
    }


@router.post("/task/{task_id}/cancel", response_model=None)
async def cancel_task(task_id: str, request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)
    try:
        task_service.get_task_for_user(task_id, user_id)
        canceled = task_service.cancel_task(task_id)
        task = task_service.get_task(task_id)
    except KeyError:
        return _json_error(404, "TASK_NOT_FOUND", "task not found", request)
    return {"task_id": task_id, "canceled": canceled, "status": task.status}


@router.get("/task/{task_id}/steps", response_model=None)
async def get_task_steps(task_id: str, request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)
    try:
        task_service.get_task_for_user(task_id, user_id)
        steps = task_service.get_task_steps(task_id)
    except KeyError:
        return _json_error(404, "TASK_NOT_FOUND", "task not found", request)
    return {
        "task_id": task_id,
        "steps": [
            {
                "id": step.id,
                "agent_name": step.agent_name,
                "step_status": step.step_status,
                "output_json": step.output_json,
                "created_at": step.created_at.isoformat(),
            }
            for step in steps
        ],
    }


@router.get("/session/{session_id}", response_model=None)
async def get_session(session_id: str, request: Request):
    session = state_manager.conversation_states.get(session_id)
    if session is None:
        return _json_error(404, SESSION_NOT_FOUND, "session not found", request)
    return session.model_dump()


@router.get("/sessions", response_model=None)
async def list_sessions(request: Request, limit: int = 20):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)
    states = task_repository.list_session_states_for_user(user_id, limit)
    return {"sessions": [_serialize_session_state(state) for state in states]}


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)

    preferences = _normalize_preferences(task_repository.get_user_preferences(user_id))
    return UserPreferencesResponse(preferences=preferences)


@router.put("/preferences", response_model=UserPreferencesResponse)
async def update_preferences(preferences: UserPreferences, request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)

    normalized = _normalize_preferences(preferences)
    task_repository.upsert_user_preferences(user_id, normalized.model_dump())
    return UserPreferencesResponse(preferences=normalized)


@router.post("/bookings", response_model=BookingRecordResponse, status_code=201)
async def create_booking(request: CreateBookingRequest, http_request: Request):
    has_auth, user_id, invalid_auth = _auth_context(http_request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", http_request)

    booking = task_repository.create_booking_record(
        user_id=user_id,
        session_id=request.session_id,
        booking_type=request.booking_type,
        item_name=request.item_name,
        amount=request.amount,
        currency=request.currency,
        status=request.status,
        payload_json=request.payload,
    )
    return BookingRecordResponse(**_serialize_booking_record(booking))


@router.get("/bookings", response_model=BookingListResponse)
async def list_bookings(request: Request, limit: int = 20, session_id: str | None = None, booking_type: str | None = None):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if invalid_auth or not has_auth or user_id is None:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)

    bookings = task_repository.list_booking_records_for_user(
        user_id,
        limit=limit,
        session_id=session_id,
        booking_type=booking_type,
    )
    return BookingListResponse(bookings=[BookingRecordResponse(**_serialize_booking_record(record)) for record in bookings])


@router.get("/plan/{session_id}", response_model=None)
async def get_plan(session_id: str, request: Request):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if has_auth and invalid_auth:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)

    owner_id = session_owner_ids.get(session_id)
    if owner_id is not None and user_id != owner_id:
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)

    plan = state_manager.current_plans.get(session_id)
    if plan is not None:
        return plan.model_dump()

    session = state_manager.conversation_states.get(session_id)
    if session is None or session.last_plan is None:
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)
    return session.last_plan


@router.get("/plan/{session_id}/history", response_model=None)
async def get_plan_history(session_id: str, request: Request, limit: int = 5):
    has_auth, user_id, invalid_auth = _auth_context(request)
    if has_auth and invalid_auth:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", request)

    owner_id = session_owner_ids.get(session_id)
    local_history = [item.model_dump() for item in state_manager.get_plan_history(session_id, limit)]

    if user_id is None:
        if owner_id is None and local_history:
            return {"session_id": session_id, "history": local_history}
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)

    if owner_id is None:
        snapshots = task_repository.get_plan_history_for_user(session_id, limit, user_id)
        if not snapshots:
            return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)
        return {"session_id": session_id, "history": _serialize_plan_snapshots(snapshots)}

    if user_id != owner_id:
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)

    if local_history:
        return {"session_id": session_id, "history": local_history}

    snapshots = task_repository.get_plan_history_for_user(session_id, limit, user_id)
    if not snapshots:
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", request)

    return {"session_id": session_id, "history": _serialize_plan_snapshots(snapshots)}


@router.post("/plan/{session_id}/revise", response_model=RevisePlanResponse)
async def revise_plan(
    session_id: str,
    request: RevisePlanRequest,
    http_request: Request,
):
    has_auth, user_id, invalid_auth = _auth_context(http_request)
    if invalid_auth:
        return _json_error(401, "UNAUTHENTICATED", "unauthenticated", http_request)

    owner_id = session_owner_ids.get(session_id)
    if session_id not in state_manager.conversation_states:
        return _json_error(404, SESSION_NOT_FOUND, "session not found", http_request)

    if owner_id is not None:
        if user_id != owner_id:
            return _json_error(404, PLAN_NOT_FOUND, "plan not found", http_request)
    elif user_id is not None:
        return _json_error(404, PLAN_NOT_FOUND, "plan not found", http_request)

    try:
        response = await plan_revision_service.revise_plan(session_id, request)
        if user_id is not None:
            _remember_preference_updates(user_id, request.updates)
        return response
    except StateError as exc:
        code = getattr(exc, "code", SESSION_NOT_FOUND if str(exc) == "session not found" else INTERNAL_ERROR)
        return _json_error(404, code, str(exc), http_request)
