import pytest

from app.db.models import Task
from app.db.repository import TaskRepository
from app.services.task_service import TaskService


class FailingQueue:
    def enqueue(self, payload):
        raise RuntimeError("queue unavailable")


def test_create_chat_task_marks_failed_when_enqueue_errors(tmp_path):
    repository = TaskRepository(f"sqlite:///{tmp_path / 'task-service.db'}")
    service = TaskService(repository=repository, queue=FailingQueue())

    with pytest.raises(RuntimeError):
        service.create_chat_task(session_id="s-queue-fail", message="hello")

    with repository._session_factory() as db:
        tasks = db.query(Task).all()
    assert len(tasks) == 1
    task = tasks[0]
    # The API should not leave enqueue-failed tasks in PENDING.
    assert task.status == "FAILED"
    assert task.error_code == "QUEUE_ENQUEUE_FAILED"
