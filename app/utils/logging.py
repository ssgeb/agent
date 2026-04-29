from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

_BASE_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # extra 字段会透传到日志记录中，便于附带 request_id、session_id 等可观测字段。
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _BASE_RECORD_KEYS and not key.startswith("_")
        }
        if extras:
            base.update(extras)
        return json.dumps(base, ensure_ascii=False, default=str)


def setup_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        root_logger.addHandler(handler)
        return

    for handler in root_logger.handlers:
        handler.setFormatter(JsonFormatter())


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
