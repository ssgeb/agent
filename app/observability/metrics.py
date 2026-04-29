from __future__ import annotations

from threading import Lock


class InMemoryMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.request_total = 0
        self.error_total = 0
        self.total_latency_ms = 0.0

    def record_request(self, latency_ms: float, is_error: bool) -> None:
        with self._lock:
            self.request_total += 1
            self.total_latency_ms += float(latency_ms)
            if is_error:
                self.error_total += 1

    def snapshot(self) -> dict[str, float | int]:
        with self._lock:
            average_latency_ms = (
                self.total_latency_ms / self.request_total if self.request_total else 0.0
            )
            return {
                "request_total": self.request_total,
                "error_total": self.error_total,
                "total_latency_ms": self.total_latency_ms,
                "average_latency_ms": average_latency_ms,
            }


metrics = InMemoryMetrics()
