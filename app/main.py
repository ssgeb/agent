from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.routes import router
from app.observability.metrics import metrics
from app.utils.error_codes import INTERNAL_ERROR, build_error
from app.utils.logging import get_logger, setup_logging
from app.middleware.prompt_injection_middleware import PromptInjectionMiddleware

setup_logging()
logger = get_logger(__name__)

app = FastAPI(title="multi-agent-travel-planner", version="0.1.0")

# 添加提示词注入防护中间件
app.add_middleware(PromptInjectionMiddleware, exempt_paths=["/health"])

app.include_router(router)
app.include_router(auth_router)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = uuid4().hex[:8]
    request.state.request_id = request_id
    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (perf_counter() - started_at) * 1000
        metrics.record_request(latency_ms=latency_ms, is_error=True)
        logger.exception(
            "request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "latency_ms": round(latency_ms, 2),
            },
        )
        response = JSONResponse(
            status_code=500,
            content=build_error(INTERNAL_ERROR, "internal error", request_id=request_id),
        )
        response.headers["X-Request-ID"] = request_id
        return response

    latency_ms = (perf_counter() - started_at) * 1000
    is_error = response.status_code >= 400
    metrics.record_request(latency_ms=latency_ms, is_error=is_error)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 2),
        },
    )
    return response
