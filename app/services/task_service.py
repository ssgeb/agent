from __future__ import annotations

from app.services.task_status import (
    TASK_CANCELED,
    TASK_PENDING,
    TASK_RETRYING,
    TASK_RUNNING,
    TASK_WAITING_INPUT,
)


class TaskService:
    def __init__(self, repository, queue) -> None:
        self.repository = repository
        self.queue = queue

    def create_chat_task(
        self,
        session_id: str,
        message: str,
        request_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        task_id = self.repository.create_task(session_id=session_id, task_type="chat", user_id=user_id)
        payload = {"task_id": task_id, "session_id": session_id, "message": message, "retry_count": 0}
        if request_id is not None:
            payload["request_id"] = request_id
        if user_id is not None:
            payload["user_id"] = user_id
        self.repository.save_task_payload(task_id, payload)
        try:
            self.queue.enqueue(payload)
        except Exception:
            self.repository.update_task_status(task_id, "FAILED", error_code="QUEUE_ENQUEUE_FAILED")
            raise
        return {"task_id": task_id, "status": TASK_PENDING, "session_id": session_id}

    def get_task(self, task_id: str):
        return self.repository.get_task(task_id)

    def get_task_for_user(self, task_id: str, user_id: str | None):
        return self.repository.get_task_for_user(task_id, user_id)

    def get_task_steps(self, task_id: str):
        return self.repository.get_task_steps(task_id)

    def cancel_task(self, task_id: str) -> bool:
        return self.repository.try_transition_task_status(
            task_id,
            TASK_CANCELED,
            allowed_from={TASK_PENDING, TASK_RUNNING, TASK_WAITING_INPUT, TASK_RETRYING},
            error_code=None,
        )
