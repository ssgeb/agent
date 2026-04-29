from __future__ import annotations

import asyncio
import inspect
from datetime import datetime

from app.services.task_status import (
    TASK_FAILED,
    TASK_PENDING,
    TASK_RETRYING,
    TASK_RUNNING,
    TASK_SUCCEEDED,
    TASK_WAITING_INPUT,
    TERMINAL_TASK_STATUSES,
)
from app.utils.logging import get_logger


logger = get_logger(__name__)


class TaskWorker:
    CHECKPOINT_NODE_ORDER = ("ingest", "planner", "finalize")

    def __init__(
        self,
        repository,
        runner,
        queue=None,
        *,
        max_retries: int = 3,
        session_lock_ttl_seconds: int = 60,
    ) -> None:
        self.repository = repository
        self.runner = runner
        self.queue = queue
        self.max_retries = max(max_retries, 0)
        self.session_lock_ttl_seconds = max(session_lock_ttl_seconds, 1)
        self._running = False

    @staticmethod
    def _retry_count(payload: dict) -> int:
        try:
            return max(int(payload.get("retry_count", 0)), 0)
        except (AttributeError, TypeError, ValueError):
            return 0

    @staticmethod
    def _trace_context(
        payload: dict,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
        **extra,
    ) -> dict:
        payload = payload if isinstance(payload, dict) else {}
        context = {
            "task_id": task_id or payload.get("task_id"),
            "session_id": session_id or payload.get("session_id"),
            "request_id": payload.get("request_id"),
        }
        context.update(extra)
        return {key: value for key, value in context.items() if value is not None}

    def _requeue(self, payload: dict, retry_count: int) -> None:
        if self.queue is None:
            return
        retry_payload = dict(payload)
        retry_payload["retry_count"] = retry_count
        self._save_task_payload(retry_payload.get("task_id"), retry_payload)
        self.queue.enqueue(retry_payload, dedupe=False)
        logger.info(
            "task requeued for retry",
            extra=self._trace_context(retry_payload, retry_count=retry_count),
        )

    def _send_to_dlq(self, payload: dict, retry_count: int, exc: Exception) -> None:
        if self.queue is None:
            return
        dlq_payload = dict(payload) if isinstance(payload, dict) else {"payload": payload}
        dlq_payload.update(
            {
                "retry_count": retry_count,
                "error": str(exc),
                "failed_at": datetime.utcnow().isoformat(),
            }
        )
        self.queue.enqueue_dlq(dlq_payload)

    def _handle_failure(self, payload: dict, task_id: str, exc: Exception) -> None:
        retry_count = self._retry_count(payload)
        self.repository.append_task_step(
            task_id,
            "worker",
            "FAILED",
            {
                "error": str(exc),
                "retry_count": retry_count,
                "checkpoint": payload.get("checkpoint") if isinstance(payload, dict) else None,
            },
        )

        if self.queue is not None and retry_count < self.max_retries:
            transitioned = self.repository.try_transition_task_status(
                task_id,
                TASK_RETRYING,
                allowed_from={TASK_RUNNING},
                error_code="WORKER_ERROR",
            )
            if not transitioned:
                return
            logger.warning(
                "task failed; scheduling retry",
                extra=self._trace_context(
                    payload,
                    task_id=task_id,
                    retry_count=retry_count,
                    max_retries=self.max_retries,
                    error=str(exc),
                ),
            )
            self._requeue(payload, retry_count + 1)
            return

        transitioned = self.repository.try_transition_task_status(
            task_id,
            TASK_FAILED,
            allowed_from={TASK_RUNNING, TASK_RETRYING},
            error_code="WORKER_ERROR",
        )
        if not transitioned:
            return
        logger.exception(
            "task failed permanently",
            extra=self._trace_context(
                payload,
                task_id=task_id,
                retry_count=retry_count,
                max_retries=self.max_retries,
                error=str(exc),
            ),
        )
        self._send_to_dlq(payload, retry_count, exc)

    def _validate_payload(self, payload: dict) -> tuple[str, str] | None:
        if not isinstance(payload, dict):
            self._send_to_dlq(payload, 0, ValueError("task payload must be a dict"))
            return None

        missing_fields = [
            field_name
            for field_name in ("task_id", "session_id")
            if not payload.get(field_name)
        ]
        if missing_fields:
            self._send_to_dlq(
                payload,
                self._retry_count(payload),
                ValueError(f"task payload missing required field(s): {', '.join(missing_fields)}"),
            )
            return None
        return str(payload["task_id"]), str(payload["session_id"])

    def _save_task_payload(self, task_id: object, payload: dict) -> None:
        if not task_id or not hasattr(self.repository, "save_task_payload"):
            return
        self.repository.save_task_payload(str(task_id), dict(payload))

    @staticmethod
    def _runner_accepts_keyword(callable_obj, keyword: str) -> bool:
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return False
        if keyword in signature.parameters:
            return True
        return any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

    @staticmethod
    def _completed_nodes(payload: dict) -> set[str]:
        checkpoint = payload.get("checkpoint") if isinstance(payload, dict) else None
        if not isinstance(checkpoint, dict):
            return set()
        completed_nodes = checkpoint.get("completed_nodes", [])
        node_outputs = checkpoint.get("node_outputs", {})
        if not isinstance(completed_nodes, list):
            return set()
        if not isinstance(node_outputs, dict):
            node_outputs = {}
        return {
            str(node)
            for node in completed_nodes
            if str(node) in node_outputs
        }

    @staticmethod
    def _merge_persisted_checkpoint(payload: dict, persisted_payload: dict | None) -> None:
        if not isinstance(persisted_payload, dict):
            return
        persisted_checkpoint = persisted_payload.get("checkpoint")
        if not isinstance(persisted_checkpoint, dict):
            return
        payload["checkpoint"] = TaskWorker._merge_checkpoints(
            payload.get("checkpoint"),
            persisted_checkpoint,
        )

    @staticmethod
    def _checkpoint_nodes(checkpoint: dict) -> list[str]:
        completed_nodes = checkpoint.get("completed_nodes", [])
        if not isinstance(completed_nodes, list):
            return []
        return [str(node) for node in completed_nodes]

    @staticmethod
    def _checkpoint_outputs(checkpoint: dict) -> dict:
        node_outputs = checkpoint.get("node_outputs", {})
        return dict(node_outputs) if isinstance(node_outputs, dict) else {}

    @classmethod
    def _ordered_checkpoint_nodes(cls, nodes: set[str], original_order: list[str]) -> list[str]:
        ordered = [node for node in cls.CHECKPOINT_NODE_ORDER if node in nodes]
        ordered.extend(node for node in original_order if node in nodes and node not in ordered)
        return ordered

    @classmethod
    def _merge_checkpoints(cls, incoming_checkpoint, persisted_checkpoint: dict) -> dict:
        if not isinstance(incoming_checkpoint, dict):
            return dict(persisted_checkpoint)

        incoming_nodes = cls._checkpoint_nodes(incoming_checkpoint)
        persisted_nodes = cls._checkpoint_nodes(persisted_checkpoint)
        completed = set(incoming_nodes) | set(persisted_nodes)
        outputs = cls._checkpoint_outputs(incoming_checkpoint)
        outputs.update(cls._checkpoint_outputs(persisted_checkpoint))

        merged = dict(incoming_checkpoint)
        merged.update(persisted_checkpoint)
        merged["completed_nodes"] = cls._ordered_checkpoint_nodes(
            completed,
            [*incoming_nodes, *persisted_nodes],
        )
        merged["node_outputs"] = outputs
        return merged

    def _emit_step_callback(self, task_id: str, payload: dict):
        def emit_step(node: str, output: dict, checkpoint: dict) -> None:
            completed_before_emit = self._completed_nodes(payload)
            payload["checkpoint"] = checkpoint
            self._save_task_payload(task_id, payload)
            if node in completed_before_emit:
                return
            self.repository.append_task_step(task_id, str(node), "SUCCEEDED", output)

        return emit_step

    def _run_chat(self, task_id: str, session_id: str, message: str, payload: dict) -> tuple[dict, bool]:
        run_chat = self.runner.run_chat
        kwargs = {"session_id": session_id, "message": message}
        emitted_steps = 0

        if self._runner_accepts_keyword(run_chat, "checkpoint"):
            kwargs["checkpoint"] = payload.get("checkpoint")
        if self._runner_accepts_keyword(run_chat, "emit_step"):
            emit_step = self._emit_step_callback(task_id, payload)

            def counted_emit(node: str, output: dict, checkpoint: dict):
                nonlocal emitted_steps
                emitted_steps += 1
                return emit_step(node, output, checkpoint)

            kwargs["emit_step"] = counted_emit

        result = asyncio.run(run_chat(**kwargs))
        if isinstance(result, dict) and isinstance(result.get("checkpoint"), dict):
            payload["checkpoint"] = result["checkpoint"]
            self._save_task_payload(task_id, payload)
        return result, emitted_steps > 0

    @staticmethod
    def _payload_for_recovery(task) -> dict:
        payload = dict(task.payload_json or {}) if isinstance(task.payload_json, dict) else {}
        payload["task_id"] = task.task_id
        payload["session_id"] = task.session_id
        payload.setdefault("message", "")
        payload.setdefault("retry_count", 0)
        return payload

    def process_one(self, payload: dict, *, requeue_on_lock_conflict: bool = True) -> bool:
        validated = self._validate_payload(payload)
        if validated is None:
            return False
        task_id, session_id = validated
        retry_count = self._retry_count(payload)
        lock_owner = f"task-worker:{id(self)}:{task_id}"
        lock_acquired = False

        try:
            task = self.repository.get_task(task_id)
        except KeyError as exc:
            self._send_to_dlq(payload, retry_count, exc)
            return False

        if task.status in TERMINAL_TASK_STATUSES:
            return False
        self._merge_persisted_checkpoint(payload, task.payload_json)
        message = payload.get("message", "")
        retry_count = self._retry_count(payload)
        self._save_task_payload(task_id, payload)
        logger.info(
            "task processing started",
            extra=self._trace_context(payload, task_id=task_id, session_id=session_id, retry_count=retry_count),
        )

        if self.queue is not None:
            lock_acquired = self.queue.acquire_session_lock(
                session_id,
                lock_owner,
                self.session_lock_ttl_seconds,
            )
            if not lock_acquired:
                if requeue_on_lock_conflict:
                    self._requeue(payload, retry_count)
                logger.info(
                    "task skipped because session lock is held",
                    extra=self._trace_context(
                        payload,
                        task_id=task_id,
                        session_id=session_id,
                        retry_count=retry_count,
                    ),
                )
                return False

        try:
            transitioned = self.repository.try_transition_task_status(
                task_id,
                TASK_RUNNING,
                allowed_from={TASK_PENDING, TASK_RETRYING, TASK_WAITING_INPUT, TASK_RUNNING},
            )
            if not transitioned:
                logger.info(
                    "task status transition skipped",
                    extra=self._trace_context(
                        payload,
                        task_id=task_id,
                        session_id=session_id,
                        retry_count=retry_count,
                    ),
                )
                return False
            try:
                result, uses_node_steps = self._run_chat(task_id, session_id, message, payload)
                if not uses_node_steps:
                    self.repository.append_task_step(task_id, "planner", "SUCCEEDED", result)
                if result.get("updated_plan") is not None:
                    plan_id = self.repository.save_plan_snapshot(
                        session_id=session_id,
                        task_id=task_id,
                        plan_json=result["updated_plan"],
                        user_id=getattr(task, "user_id", None),
                    )
                    logger.info(
                        "plan snapshot saved",
                        extra=self._trace_context(
                            payload,
                            task_id=task_id,
                            session_id=session_id,
                            plan_id=plan_id,
                        ),
                    )
                if result.get("needs_user_input") is True:
                    self.repository.try_transition_task_status(
                        task_id,
                        TASK_WAITING_INPUT,
                        allowed_from={TASK_RUNNING},
                    )
                    logger.info(
                        "task waiting for user input",
                        extra=self._trace_context(payload, task_id=task_id, session_id=session_id),
                    )
                else:
                    self.repository.try_transition_task_status(
                        task_id,
                        TASK_SUCCEEDED,
                        allowed_from={TASK_RUNNING},
                    )
                    logger.info(
                        "task succeeded",
                        extra=self._trace_context(payload, task_id=task_id, session_id=session_id),
                    )
            except Exception as exc:
                self._handle_failure(payload, task_id, exc)
            return True
        finally:
            if lock_acquired and self.queue is not None:
                self.queue.release_session_lock(session_id, lock_owner)

    def consume_once(self) -> str | None:
        """消费一个队列任务并执行，返回 task_id；若队列为空返回 None。"""
        if self.queue is None:
            return None
        payload = self.queue.dequeue()
        if payload is None:
            return None
        if not self.process_one(payload):
            return None
        return payload.get("task_id")

    def run_loop(
        self,
        *,
        max_iterations: int | None = None,
        blocking_timeout_seconds: float = 1.0,
    ) -> int:
        """常驻消费循环。

        返回本轮取出并交给 worker 处理的有效任务数量。

        坏 payload、锁冲突、终态任务等 `process_one` 返回 False 的情况不计入。
        """
        if self.queue is None:
            return 0

        self._running = True
        consumed = 0
        iterations = 0
        while self._running:
            if max_iterations is not None and iterations >= max_iterations:
                break
            iterations += 1
            payload = self.queue.blocking_dequeue(timeout_seconds=blocking_timeout_seconds)
            if payload is None:
                continue
            if self.process_one(payload):
                consumed += 1
        self._running = False
        return consumed

    def stop(self) -> None:
        self._running = False

    def resume_incomplete_tasks(self, *, stale_seconds: float | None = None) -> list[str]:
        recovered: list[str] = []
        for task in self.repository.list_recoverable_tasks(stale_seconds=stale_seconds):
            if self.process_one(
                self._payload_for_recovery(task),
                requeue_on_lock_conflict=False,
            ):
                recovered.append(task.task_id)
        return recovered
