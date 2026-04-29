import threading
import time
from datetime import datetime, timedelta

from app.db.models import Task
from app.workers.task_worker import TaskWorker


def test_worker_updates_task_and_steps_on_success(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    task_id = repository.create_task(session_id="s-001", task_type="chat")

    worker = TaskWorker(**fake_worker_deps)
    worker.process_one({"task_id": task_id, "session_id": "s-001", "message": "上海到杭州两日酒店"})

    task = repository.get_task(task_id)
    steps = repository.get_task_steps(task_id)

    assert task.status == "SUCCEEDED"
    assert len(steps) > 0
    assert task.payload_json["message"] == "上海到杭州两日酒店"


def test_worker_can_resume_running_task(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    repository.seed_running_task(task_id="t-resume", session_id="s-1")

    worker = TaskWorker(**fake_worker_deps)
    recovered = worker.resume_incomplete_tasks()

    assert "t-resume" in recovered
    assert repository.get_task("t-resume").status in {"SUCCEEDED", "WAITING_INPUT"}
    assert len(repository.get_task_steps("t-resume")) > 0


def test_worker_resume_uses_persisted_message_payload(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    payload = {
        "task_id": "t-resume-message",
        "session_id": "s-resume-message",
        "message": "persisted message",
        "retry_count": 1,
    }
    repository.seed_running_task(
        task_id="t-resume-message",
        session_id="s-resume-message",
        payload_json=payload,
    )

    class RecordingRunner:
        def __init__(self) -> None:
            self.messages: list[str] = []

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.messages.append(message)
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = RecordingRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=fake_worker_deps["queue"])

    assert worker.resume_incomplete_tasks() == ["t-resume-message"]
    assert runner.messages == ["persisted message"]
    assert repository.get_task_steps("t-resume-message")[0].output_json["response"] == "persisted message"


def test_worker_resume_uses_persisted_retry_count(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    payload = {
        "task_id": "t-resume-retry-count",
        "session_id": "s-resume-retry-count",
        "message": "permanent failure",
        "retry_count": 2,
    }
    repository.seed_running_task(
        task_id="t-resume-retry-count",
        session_id="s-resume-retry-count",
        payload_json=payload,
    )

    class AlwaysFailsRunner:
        async def run_chat(self, session_id: str, message: str) -> dict:
            raise RuntimeError(f"failed message: {message}")

    worker = TaskWorker(
        repository=repository,
        runner=AlwaysFailsRunner(),
        queue=queue,
        max_retries=2,
    )

    assert worker.resume_incomplete_tasks() == ["t-resume-retry-count"]
    assert repository.get_task("t-resume-retry-count").status == "FAILED"
    assert queue.size() == 0
    dlq_payload = queue.dequeue_dlq()
    assert dlq_payload["retry_count"] == 2
    assert "permanent failure" in dlq_payload["message"]


def test_worker_recovers_stale_pending_task_with_persisted_payload(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    payload = {
        "task_id": "t-stale-pending",
        "session_id": "s-stale-pending",
        "message": "recover me after queue pop crash",
        "retry_count": 0,
    }
    with repository._session_factory() as db:
        db.add(
            Task(
                task_id="t-stale-pending",
                session_id="s-stale-pending",
                task_type="chat",
                status="PENDING",
                payload_json=payload,
                updated_at=datetime.utcnow() - timedelta(seconds=120),
            )
        )
        db.commit()

    class RecordingRunner:
        def __init__(self) -> None:
            self.messages: list[str] = []

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.messages.append(message)
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = RecordingRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=fake_worker_deps["queue"])

    assert worker.resume_incomplete_tasks(stale_seconds=60) == ["t-stale-pending"]
    assert runner.messages == ["recover me after queue pop crash"]
    assert repository.get_task("t-stale-pending").status == "SUCCEEDED"


def test_worker_does_not_recover_non_stale_running_task(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    repository.seed_running_task(
        task_id="t-healthy-running",
        session_id="s-healthy-running",
        payload_json={
            "task_id": "t-healthy-running",
            "session_id": "s-healthy-running",
            "message": "still running",
        },
    )

    class CountingRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.calls += 1
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = CountingRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=fake_worker_deps["queue"])

    assert worker.resume_incomplete_tasks(stale_seconds=60) == []
    assert runner.calls == 0
    assert repository.get_task("t-healthy-running").status == "RUNNING"
    assert repository.get_task_steps("t-healthy-running") == []


def test_resume_does_not_requeue_when_running_task_lock_is_held(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    repository.seed_running_task(
        task_id="t-stale-running-locked",
        session_id="s-stale-running-locked",
        payload_json={
            "task_id": "t-stale-running-locked",
            "session_id": "s-stale-running-locked",
            "message": "still running elsewhere",
        },
    )
    with repository._session_factory() as db:
        task = db.get(Task, "t-stale-running-locked")
        task.updated_at = datetime.utcnow() - timedelta(seconds=120)
        db.commit()

    assert queue.acquire_session_lock(
        "s-stale-running-locked",
        owner="external-worker",
        ttl_seconds=5,
    )

    class NeverCalledRunner:
        async def run_chat(self, session_id: str, message: str) -> dict:
            raise AssertionError("runner should not be called when lock is held")

    worker = TaskWorker(repository=repository, runner=NeverCalledRunner(), queue=queue)
    assert worker.resume_incomplete_tasks(stale_seconds=60) == []
    assert queue.size() == 0
    assert repository.get_task("t-stale-running-locked").status == "RUNNING"


def test_worker_consume_once_reads_from_queue(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]

    task_id = repository.create_task(session_id="s-queue", task_type="chat")
    queue.enqueue({"task_id": task_id, "session_id": "s-queue", "message": "上海到杭州两日酒店"})

    worker = TaskWorker(**fake_worker_deps)
    consumed_task_id = worker.consume_once()

    assert consumed_task_id == task_id
    assert repository.get_task(task_id).status == "SUCCEEDED"


def test_worker_run_loop_consumes_multiple_tasks(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    worker = TaskWorker(**fake_worker_deps)

    task_ids = []
    for idx in range(3):
        task_id = repository.create_task(session_id=f"s-loop-{idx}", task_type="chat")
        queue.enqueue({"task_id": task_id, "session_id": f"s-loop-{idx}", "message": "上海到杭州两日酒店"})
        task_ids.append(task_id)

    consumed = worker.run_loop(max_iterations=3, blocking_timeout_seconds=0.01)
    assert consumed == 3
    for task_id in task_ids:
        assert repository.get_task(task_id).status == "SUCCEEDED"


def test_worker_stop_can_break_loop(fake_worker_deps):
    worker = TaskWorker(**fake_worker_deps)
    result_holder: dict[str, int] = {}

    def _run():
        result_holder["consumed"] = worker.run_loop(
            max_iterations=None,
            blocking_timeout_seconds=0.01,
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.03)
    worker.stop()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert result_holder.get("consumed", 0) == 0


def test_worker_sets_waiting_input_when_runner_requests_input(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    task_id = repository.create_task(session_id="s-wait", task_type="chat")

    class WaitingRunner:
        async def run_chat(self, session_id: str, message: str) -> dict:
            return {
                "session_id": session_id,
                "response": "请补充预算",
                "updated_plan": {"transport_plan": None, "hotel_plan": None, "itinerary_plan": None},
                "pending_questions": ["预算上限多少？"],
                "needs_user_input": True,
            }

    worker = TaskWorker(repository=repository, runner=WaitingRunner(), queue=fake_worker_deps["queue"])
    worker.process_one({"task_id": task_id, "session_id": "s-wait", "message": "帮我规划"})

    assert repository.get_task(task_id).status == "WAITING_INPUT"


def test_worker_skips_canceled_task(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    task_id = repository.create_task(session_id="s-cancel", task_type="chat")
    repository.update_task_status(task_id, "CANCELED")

    worker = TaskWorker(**fake_worker_deps)
    worker.process_one({"task_id": task_id, "session_id": "s-cancel", "message": "上海到杭州两日酒店"})

    assert repository.get_task(task_id).status == "CANCELED"
    assert repository.get_task_steps(task_id) == []


def test_worker_retries_failed_task_then_succeeds(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    task_id = repository.create_task(session_id="s-retry", task_type="chat")
    queue.enqueue({"task_id": task_id, "session_id": "s-retry", "message": "retry me"})

    class FailsOnceRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary planner failure")
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = FailsOnceRunner()
    worker = TaskWorker(
        repository=repository,
        runner=runner,
        queue=queue,
        max_retries=1,
    )

    assert worker.consume_once() == task_id
    assert repository.get_task(task_id).status == "RETRYING"
    assert repository.get_task(task_id).payload_json["retry_count"] == 1
    assert queue.size() == 1

    assert worker.consume_once() == task_id
    assert repository.get_task(task_id).status == "SUCCEEDED"
    assert runner.calls == 2


def test_worker_retry_uses_checkpoint_without_duplicate_completed_steps(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    task_id = repository.create_task(session_id="s-node-retry", task_type="chat")
    queue.enqueue({"task_id": task_id, "session_id": "s-node-retry", "message": "retry by node"})

    class FailsAfterIngestRunner:
        def __init__(self) -> None:
            self.checkpoints: list[dict] = []

        async def run_chat(self, session_id: str, message: str, checkpoint=None, emit_step=None) -> dict:
            latest_checkpoint = dict(checkpoint or {})
            self.checkpoints.append(latest_checkpoint)
            completed = set(latest_checkpoint.get("completed_nodes", []))

            if "ingest" not in completed:
                ingest_checkpoint = {
                    "completed_nodes": ["ingest"],
                    "node_outputs": {
                        "ingest": {"session_id": session_id, "message": message},
                    },
                }
                emit_step("ingest", {"session_id": session_id, "message": message}, ingest_checkpoint)
                raise RuntimeError("temporary failure after ingest")

            planner_checkpoint = {
                "completed_nodes": ["ingest", "planner"],
                "node_outputs": {
                    **latest_checkpoint.get("node_outputs", {}),
                    "planner": {
                        "session_id": session_id,
                        "response": "planned",
                        "updated_plan": None,
                        "pending_questions": [],
                        "needs_user_input": False,
                    },
                },
            }
            emit_step("planner", planner_checkpoint["node_outputs"]["planner"], planner_checkpoint)
            final_checkpoint = {
                "completed_nodes": ["ingest", "planner", "finalize"],
                "node_outputs": {
                    **planner_checkpoint["node_outputs"],
                    "finalize": planner_checkpoint["node_outputs"]["planner"],
                },
            }
            emit_step("finalize", final_checkpoint["node_outputs"]["finalize"], final_checkpoint)
            return {
                **final_checkpoint["node_outputs"]["finalize"],
                "checkpoint": final_checkpoint,
            }

    runner = FailsAfterIngestRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=queue, max_retries=1)

    assert worker.consume_once() == task_id
    assert repository.get_task(task_id).status == "RETRYING"
    assert repository.get_task(task_id).payload_json["checkpoint"]["completed_nodes"] == ["ingest"]

    assert worker.consume_once() == task_id
    assert repository.get_task(task_id).status == "SUCCEEDED"

    step_names = [step.agent_name for step in repository.get_task_steps(task_id)]
    assert step_names.count("ingest") == 1
    assert step_names.count("planner") == 1
    assert step_names.count("finalize") == 1
    assert runner.checkpoints[1]["completed_nodes"] == ["ingest"]


def test_worker_reconciles_stale_queue_checkpoint_with_persisted_payload(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    persisted_checkpoint = {
        "completed_nodes": ["ingest", "planner"],
        "node_outputs": {
            "ingest": {"session_id": "s-reconcile", "message": "stale queue"},
            "planner": {
                "session_id": "s-reconcile",
                "response": "from persisted planner",
                "updated_plan": None,
                "pending_questions": [],
                "needs_user_input": False,
            },
        },
    }
    stale_checkpoint = {
        "completed_nodes": ["ingest"],
        "node_outputs": {
            "ingest": {"session_id": "s-reconcile", "message": "stale queue"},
        },
    }
    task_id = repository.create_task(
        session_id="s-reconcile",
        task_type="chat",
        payload_json={
            "task_id": "placeholder",
            "session_id": "s-reconcile",
            "message": "stale queue",
            "retry_count": 0,
            "checkpoint": persisted_checkpoint,
        },
    )
    repository.save_task_payload(
        task_id,
        {
            "task_id": task_id,
            "session_id": "s-reconcile",
            "message": "stale queue",
            "retry_count": 0,
            "checkpoint": persisted_checkpoint,
        },
    )
    queue.enqueue(
        {
            "task_id": task_id,
            "session_id": "s-reconcile",
            "message": "stale queue",
            "retry_count": 0,
            "checkpoint": stale_checkpoint,
        },
        dedupe=False,
    )

    class RecordingRunner:
        def __init__(self) -> None:
            self.checkpoints: list[dict] = []

        async def run_chat(self, session_id: str, message: str, checkpoint=None, emit_step=None) -> dict:
            self.checkpoints.append(checkpoint)
            final_checkpoint = {
                "completed_nodes": ["ingest", "planner", "finalize"],
                "node_outputs": {
                    **checkpoint["node_outputs"],
                    "finalize": checkpoint["node_outputs"]["planner"],
                },
            }
            emit_step("finalize", final_checkpoint["node_outputs"]["finalize"], final_checkpoint)
            return {**final_checkpoint["node_outputs"]["finalize"], "checkpoint": final_checkpoint}

    runner = RecordingRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=queue)

    assert worker.consume_once() == task_id

    assert runner.checkpoints[0]["completed_nodes"] == ["ingest", "planner"]
    assert repository.get_task(task_id).payload_json["checkpoint"]["completed_nodes"] == [
        "ingest",
        "planner",
        "finalize",
    ]


def test_worker_with_kwargs_runner_falls_back_to_planner_step_backfill(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    task_id = repository.create_task(session_id="s-kwargs-runner", task_type="chat")

    class KwargsRunner:
        async def run_chat(self, session_id: str, message: str, **kwargs) -> dict:
            return {
                "session_id": session_id,
                "response": message,
                "updated_plan": None,
                "pending_questions": [],
                "needs_user_input": False,
            }

    worker = TaskWorker(repository=repository, runner=KwargsRunner(), queue=fake_worker_deps["queue"])
    assert worker.process_one(
        {"task_id": task_id, "session_id": "s-kwargs-runner", "message": "hello kwargs"}
    )

    steps = repository.get_task_steps(task_id)
    assert len(steps) == 1
    assert steps[0].agent_name == "planner"
    assert steps[0].output_json["response"] == "hello kwargs"


def test_worker_emits_step_when_checkpoint_completed_without_output(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    task_id = repository.create_task(session_id="s-partial-checkpoint", task_type="chat")

    class PartialCheckpointRunner:
        async def run_chat(self, session_id: str, message: str, checkpoint=None, emit_step=None) -> dict:
            assert isinstance(checkpoint, dict)
            if emit_step is not None:
                emit_step(
                    "planner",
                    {"session_id": session_id, "response": message},
                    {
                        "completed_nodes": ["ingest", "planner"],
                        "node_outputs": {
                            "ingest": {"session_id": session_id, "message": message},
                            "planner": {"session_id": session_id, "response": message},
                        },
                        "version": 1,
                    },
                )
            return {
                "session_id": session_id,
                "response": message,
                "updated_plan": None,
                "pending_questions": [],
                "needs_user_input": False,
                "checkpoint": {
                    "completed_nodes": ["ingest", "planner"],
                    "node_outputs": {
                        "ingest": {"session_id": session_id, "message": message},
                        "planner": {"session_id": session_id, "response": message},
                    },
                    "version": 1,
                },
            }

    worker = TaskWorker(
        repository=repository,
        runner=PartialCheckpointRunner(),
        queue=fake_worker_deps["queue"],
    )
    payload = {
        "task_id": task_id,
        "session_id": "s-partial-checkpoint",
        "message": "replayed planner",
        "checkpoint": {
            "completed_nodes": ["ingest", "planner"],
            "node_outputs": {"ingest": {"session_id": "s-partial-checkpoint", "message": "x"}},
            "version": 1,
        },
    }
    assert worker.process_one(payload)

    steps = repository.get_task_steps(task_id)
    planner_steps = [step for step in steps if step.agent_name == "planner"]
    assert len(planner_steps) == 1
    assert planner_steps[0].output_json["response"] == "replayed planner"


def test_worker_sends_task_to_dlq_after_retry_limit(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    task_id = repository.create_task(session_id="s-dlq", task_type="chat")
    queue.enqueue({"task_id": task_id, "session_id": "s-dlq", "message": "fail"})

    class AlwaysFailsRunner:
        async def run_chat(self, session_id: str, message: str) -> dict:
            raise RuntimeError("permanent planner failure")

    worker = TaskWorker(
        repository=repository,
        runner=AlwaysFailsRunner(),
        queue=queue,
        max_retries=1,
    )

    assert worker.consume_once() == task_id
    assert repository.get_task(task_id).status == "RETRYING"

    assert worker.consume_once() == task_id
    task = repository.get_task(task_id)
    assert task.status == "FAILED"
    assert task.error_code == "WORKER_ERROR"
    assert queue.dlq_size() == 1
    assert queue.dequeue_dlq()["task_id"] == task_id


def test_session_lock_blocks_same_session_concurrent_execution(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    first_task_id = repository.create_task(session_id="s-lock", task_type="chat")
    second_task_id = repository.create_task(session_id="s-lock", task_type="chat")
    started = threading.Event()
    release_runner = threading.Event()

    class SlowRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.calls += 1
            started.set()
            release_runner.wait(timeout=1.0)
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = SlowRunner()
    worker = TaskWorker(
        repository=repository,
        runner=runner,
        queue=queue,
        session_lock_ttl_seconds=5,
    )

    first_thread = threading.Thread(
        target=worker.process_one,
        args=({"task_id": first_task_id, "session_id": "s-lock", "message": "first"},),
        daemon=True,
    )
    first_thread.start()
    assert started.wait(timeout=1.0)

    worker.process_one({"task_id": second_task_id, "session_id": "s-lock", "message": "second"})

    assert runner.calls == 1
    assert repository.get_task(second_task_id).status == "PENDING"
    assert queue.size() == 1

    release_runner.set()
    first_thread.join(timeout=1.0)
    assert not first_thread.is_alive()


def test_canceled_task_status_is_not_overwritten_by_running_worker(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    task_id = repository.create_task(session_id="s-cancel-race", task_type="chat")
    started = threading.Event()
    release_runner = threading.Event()

    class SlowRunner:
        async def run_chat(self, session_id: str, message: str) -> dict:
            started.set()
            release_runner.wait(timeout=1.0)
            return {"session_id": session_id, "response": message, "updated_plan": None}

    worker = TaskWorker(repository=repository, runner=SlowRunner(), queue=queue)
    thread = threading.Thread(
        target=worker.process_one,
        args=({"task_id": task_id, "session_id": "s-cancel-race", "message": "cancel me"},),
        daemon=True,
    )
    thread.start()
    assert started.wait(timeout=1.0)

    assert repository.try_transition_task_status(
        task_id,
        "CANCELED",
        allowed_from={"RUNNING"},
    )

    release_runner.set()
    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert repository.get_task(task_id).status == "CANCELED"


def test_queue_idempotency_key_prevents_duplicate_execution(fake_worker_deps):
    repository = fake_worker_deps["repository"]
    queue = fake_worker_deps["queue"]
    task_id = repository.create_task(session_id="s-idem", task_type="chat")
    payload = {
        "task_id": task_id,
        "session_id": "s-idem",
        "message": "only once",
        "idempotency_key": "idem:s-idem:only-once",
    }

    assert queue.enqueue(payload) is True
    assert queue.enqueue(dict(payload)) is False

    class CountingRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run_chat(self, session_id: str, message: str) -> dict:
            self.calls += 1
            return {"session_id": session_id, "response": message, "updated_plan": None}

    runner = CountingRunner()
    worker = TaskWorker(repository=repository, runner=runner, queue=queue)

    assert worker.run_loop(max_iterations=2, blocking_timeout_seconds=0.01) == 1
    assert runner.calls == 1
    assert repository.get_task(task_id).status == "SUCCEEDED"


def test_queue_idempotency_key_expires_for_local_queue():
    from app.queue.redis_queue import RedisQueue

    queue = RedisQueue(redis_url=None, idempotency_key_ttl_seconds=0.01)
    payload = {"task_id": "t-ttl", "session_id": "s-ttl", "idempotency_key": "idem:ttl"}

    assert queue.enqueue(payload) is True
    assert queue.enqueue(dict(payload)) is False

    time.sleep(0.02)

    assert queue.enqueue(dict(payload)) is True


def test_worker_sends_payload_missing_required_fields_to_dlq(fake_worker_deps):
    queue = fake_worker_deps["queue"]
    worker = TaskWorker(**fake_worker_deps)

    assert worker.process_one({"session_id": "s-bad", "message": "missing task"}) is False

    assert queue.dlq_size() == 1
    dlq_payload = queue.dequeue_dlq()
    assert dlq_payload["session_id"] == "s-bad"
    assert "task_id" in dlq_payload["error"]


def test_worker_sends_missing_task_to_dlq(fake_worker_deps):
    queue = fake_worker_deps["queue"]
    worker = TaskWorker(**fake_worker_deps)

    assert worker.process_one({"task_id": "missing-task", "session_id": "s-missing"}) is False

    assert queue.dlq_size() == 1
    dlq_payload = queue.dequeue_dlq()
    assert dlq_payload["task_id"] == "missing-task"
    assert "Task not found" in dlq_payload["error"]


def test_consume_once_handles_bad_payload_without_crashing(fake_worker_deps):
    queue = fake_worker_deps["queue"]
    worker = TaskWorker(**fake_worker_deps)
    queue.enqueue({"session_id": "s-consume-bad"}, dedupe=False)

    assert worker.consume_once() is None

    assert queue.dlq_size() == 1


def test_redis_dequeue_sends_malformed_json_to_dlq():
    from app.queue.redis_queue import RedisQueue

    class FakeRedis:
        def __init__(self) -> None:
            self.queue = ["{not-json"]
            self.dlq: list[str] = []

        def lpop(self, name: str):
            if name.endswith(":dlq"):
                return self.dlq.pop(0) if self.dlq else None
            return self.queue.pop(0) if self.queue else None

        def rpush(self, name: str, value: str) -> None:
            if name.endswith(":dlq"):
                self.dlq.append(value)

        def llen(self, name: str) -> int:
            return len(self.dlq if name.endswith(":dlq") else self.queue)

    queue = RedisQueue(redis_url=None)
    queue._redis = FakeRedis()

    assert queue.dequeue() is None
    assert queue.dlq_size() == 1
    dlq_payload = queue.dequeue_dlq()
    assert dlq_payload["raw"] == "{not-json"
    assert "error" in dlq_payload


def test_redis_idempotency_key_uses_ttl_when_enqueued():
    from app.queue.redis_queue import RedisQueue

    class FakeRedis:
        def __init__(self) -> None:
            self.set_calls: list[dict] = []
            self.values: dict[str, str] = {}
            self.queue: list[str] = []

        def set(self, key: str, value: str, **kwargs) -> bool:
            self.set_calls.append({"key": key, "value": value, **kwargs})
            if kwargs.get("nx") and key in self.values:
                return False
            self.values[key] = value
            return True

        def rpush(self, name: str, value: str) -> None:
            self.queue.append(value)

        def delete(self, key: str) -> None:
            self.values.pop(key, None)

    queue = RedisQueue(redis_url=None, idempotency_key_ttl_seconds=12)
    queue._redis = FakeRedis()

    assert queue.enqueue({"task_id": "t-redis-ttl", "idempotency_key": "idem:redis"}) is True

    assert queue._redis.set_calls[0]["nx"] is True
    assert queue._redis.set_calls[0]["px"] == 12_000


def test_routes_pass_settings_idempotency_ttl_to_queue(monkeypatch):
    import importlib

    from app.api import routes

    with monkeypatch.context() as patched:
        patched.setenv("IDEMPOTENCY_KEY_TTL_SECONDS", "7")
        reloaded_routes = importlib.reload(routes)

        assert reloaded_routes.settings.idempotency_key_ttl_seconds == 7
        assert reloaded_routes.task_queue.idempotency_key_ttl_seconds == 7

    importlib.reload(routes)
