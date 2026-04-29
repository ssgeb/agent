from __future__ import annotations

from app.agents import HotelAgent, ItineraryAgent, PlannerAgent, TransportAgent
from app.config.settings import Settings
from app.db import TaskRepository
from app.orchestration.stategraph_runner import StateGraphRunner
from app.queue.redis_queue import RedisQueue
from app.services import ChatService
from app.state import StateManager
from app.tools import create_tool_provider
from app.utils.logging import get_logger
from app.workers.task_worker import TaskWorker


logger = get_logger(__name__)


def build_worker(settings: Settings | None = None) -> TaskWorker:
    settings = settings or Settings()
    state_manager = StateManager()
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
    repository = TaskRepository(settings.resolved_database_url)
    queue = RedisQueue(
        redis_url=settings.redis_url or None,
        idempotency_key_ttl_seconds=settings.idempotency_key_ttl_seconds,
    )
    runner = StateGraphRunner(chat_service=chat_service)
    return TaskWorker(
        repository=repository,
        runner=runner,
        queue=queue,
        max_retries=settings.max_task_retries,
        session_lock_ttl_seconds=settings.session_lock_ttl_seconds,
    )


def main() -> None:
    settings = Settings()
    worker = build_worker(settings)
    logger.info(
        "task worker starting",
        extra={
            "database_url": settings.resolved_database_url,
            "redis_enabled": bool(settings.redis_url),
            "max_task_retries": settings.max_task_retries,
            "session_lock_ttl_seconds": settings.session_lock_ttl_seconds,
        },
    )
    try:
        worker.run_loop()
    except KeyboardInterrupt:
        logger.info("task worker stopping")
        worker.stop()


if __name__ == "__main__":
    main()
