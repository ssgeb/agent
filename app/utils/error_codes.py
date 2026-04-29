from __future__ import annotations

"""统一错误码与错误响应构造。"""

SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
PLAN_NOT_FOUND = "PLAN_NOT_FOUND"
INTERNAL_ERROR = "INTERNAL_ERROR"
PROMPT_INJECTION_DETECTED = "PROMPT_INJECTION_DETECTED"
PROMPT_SANITIZE_REQUIRED = "PROMPT_SANITIZE_REQUIRED"


def build_error(
    code: str,
    message: str,
    request_id: str | None = None,
    details: list | None = None
) -> dict:
    error = {
        "code": code,
        "message": message,
        "request_id": request_id,
    }
    if details:
        error["details"] = details
    return error
