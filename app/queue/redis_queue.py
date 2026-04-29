from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any


class RedisQueue:
    """Redis 队列封装；无 Redis 时自动降级为进程内队列（用于本地测试）。"""

    def __init__(
        self,
        redis_url: str | None = None,
        queue_name: str = "agent:tasks",
        idempotency_key_ttl_seconds: float = 24 * 60 * 60,
    ) -> None:
        self.queue_name = queue_name
        self.dlq_name = f"{queue_name}:dlq"
        self.idempotency_key_ttl_seconds = max(float(idempotency_key_ttl_seconds), 0.001)
        self._local_queue: deque[dict[str, Any]] = deque()
        self._local_dlq: deque[dict[str, Any]] = deque()
        self._local_idempotency_keys: dict[str, float] = {}
        self._local_session_locks: dict[str, tuple[str, float]] = {}
        self._lock = Lock()
        self._redis = None
        if redis_url:
            try:
                import redis  # type: ignore

                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    def _idempotency_key(self, key: str) -> str:
        return f"{self.queue_name}:idempotency:{key}"

    def _session_lock_key(self, session_id: str) -> str:
        return f"{self.queue_name}:session-lock:{session_id}"

    def _cleanup_local_idempotency_keys_locked(self) -> int:
        now = time.monotonic()
        expired_keys = [
            key for key, expires_at in self._local_idempotency_keys.items() if expires_at <= now
        ]
        for key in expired_keys:
            self._local_idempotency_keys.pop(key, None)
        return len(expired_keys)

    def cleanup_idempotency_keys(self) -> int:
        """Remove expired local idempotency keys and return the removed count.

        Redis-backed queues rely on Redis key TTLs; the explicit cleanup path is
        needed for the in-memory fallback so long-lived local processes do not
        grow the dedupe set forever.
        """
        if self._redis is not None:
            return 0
        with self._lock:
            return self._cleanup_local_idempotency_keys_locked()

    def _json_error_dlq_payload(self, raw: str, exc: Exception) -> dict[str, Any]:
        return {
            "raw": raw,
            "error": str(exc),
            "failed_at": datetime.utcnow().isoformat(),
        }

    def _decode_redis_payload(self, raw: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            self.enqueue_dlq(self._json_error_dlq_payload(raw, exc))
            return None
        if not isinstance(payload, dict):
            self.enqueue_dlq(
                self._json_error_dlq_payload(raw, ValueError("queue payload must be a JSON object"))
            )
            return None
        return payload

    def enqueue(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        dedupe: bool = True,
    ) -> bool:
        """Enqueue a task, optionally deduplicating by an idempotency key.

        Returns True when the payload was queued and False when it was skipped
        because the idempotency key was already observed.
        """
        dedupe_key = idempotency_key or payload.get("idempotency_key") or payload.get("dedupe_key")
        dedupe_key = str(dedupe_key) if dedupe and dedupe_key is not None else None
        if self._redis is not None:
            redis_idempotency_key = None
            if dedupe_key is not None:
                redis_idempotency_key = self._idempotency_key(dedupe_key)
                if not self._redis.set(
                    redis_idempotency_key,
                    "1",
                    nx=True,
                    px=max(int(self.idempotency_key_ttl_seconds * 1000), 1),
                ):
                    return False
            try:
                self._redis.rpush(self.queue_name, json.dumps(payload, ensure_ascii=False))
            except Exception:
                if redis_idempotency_key is not None:
                    self._redis.delete(redis_idempotency_key)
                raise
            return True
        with self._lock:
            self._cleanup_local_idempotency_keys_locked()
            if dedupe_key is not None:
                if dedupe_key in self._local_idempotency_keys:
                    return False
                self._local_idempotency_keys[dedupe_key] = (
                    time.monotonic() + self.idempotency_key_ttl_seconds
                )
            self._local_queue.append(dict(payload))
        return True

    def enqueue_dlq(self, payload: dict[str, Any]) -> None:
        if self._redis is not None:
            self._redis.rpush(self.dlq_name, json.dumps(payload, ensure_ascii=False))
            return
        with self._lock:
            self._local_dlq.append(dict(payload))

    def dequeue_dlq(self) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = self._redis.lpop(self.dlq_name)
            return None if raw is None else json.loads(raw)
        with self._lock:
            if not self._local_dlq:
                return None
            return self._local_dlq.popleft()

    def dlq_size(self) -> int:
        if self._redis is not None:
            return int(self._redis.llen(self.dlq_name))
        with self._lock:
            return len(self._local_dlq)

    def acquire_session_lock(self, session_id: str, owner: str, ttl_seconds: float) -> bool:
        ttl_seconds = max(float(ttl_seconds), 0.001)
        if self._redis is not None:
            return bool(
                self._redis.set(
                    self._session_lock_key(session_id),
                    owner,
                    nx=True,
                    ex=max(int(ttl_seconds), 1),
                )
            )

        now = time.monotonic()
        expires_at = now + ttl_seconds
        with self._lock:
            current = self._local_session_locks.get(session_id)
            if current is not None:
                current_owner, current_expires_at = current
                if current_expires_at <= now:
                    self._local_session_locks.pop(session_id, None)
                elif current_owner != owner:
                    return False
            self._local_session_locks[session_id] = (owner, expires_at)
            return True

    def release_session_lock(self, session_id: str, owner: str) -> bool:
        if self._redis is not None:
            script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            end
            return 0
            """
            return bool(self._redis.eval(script, 1, self._session_lock_key(session_id), owner))

        with self._lock:
            current = self._local_session_locks.get(session_id)
            if current is None:
                return False
            current_owner, current_expires_at = current
            if current_expires_at <= time.monotonic():
                self._local_session_locks.pop(session_id, None)
                return False
            if current_owner != owner:
                return False
            self._local_session_locks.pop(session_id, None)
            return True

    def dequeue(self) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = self._redis.lpop(self.queue_name)
            return None if raw is None else self._decode_redis_payload(raw)
        with self._lock:
            if not self._local_queue:
                return None
            return self._local_queue.popleft()

    def blocking_dequeue(self, timeout_seconds: float = 1.0) -> dict[str, Any] | None:
        """阻塞消费一个任务。

        Redis 模式下使用 BRPOP，进程内降级模式下用短轮询模拟阻塞行为。
        """
        if self._redis is not None:
            result = self._redis.blpop(self.queue_name, timeout=max(int(timeout_seconds), 1))
            if result is None:
                return None
            _, raw = result
            return self._decode_redis_payload(raw)

        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        while time.monotonic() < deadline:
            payload = self.dequeue()
            if payload is not None:
                return payload
            time.sleep(0.01)
        return None

    def size(self) -> int:
        if self._redis is not None:
            return int(self._redis.llen(self.queue_name))
        with self._lock:
            return len(self._local_queue)
