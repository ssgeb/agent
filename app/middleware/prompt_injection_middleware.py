"""
提示词注入防护中间件

用于在API入口处检测和防止提示词注入攻击
"""

from typing import Callable, Awaitable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import json

from app.utils.prompt_injection_detector import detect_prompt_injection, InjectionSeverity
from app.utils.error_codes import PROMPT_INJECTION_DETECTED, build_error


class PromptInjectionMiddleware(BaseHTTPMiddleware):
    """提示词注入防护中间件"""

    def __init__(self, app, exempt_paths: list = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        ]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # 检查是否是需要防护的路径
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # 只处理POST请求的聊天接口
        if request.method == "POST":
            if request.url.path in ["/chat", "/chat/async"]:
                # 读取请求体
                body = await request.body()
                try:
                    # 尝试解析JSON
                    data = json.loads(body)

                    # 检查是否有消息字段
                    message = data.get("message", "")
                    if isinstance(message, str) and message.strip():
                        # 检测注入攻击
                        result = detect_prompt_injection(message)

                        # 如果风险等级过高，拒绝请求
                        if result["risk_level"] in ["high", "critical"]:
                            return JSONResponse(
                                status_code=400,
                                content=build_error(
                                    PROMPT_INJECTION_DETECTED,
                                    "检测到潜在的安全威胁，请求被拒绝",
                                    request_id=getattr(request.state, "request_id", None)
                                )
                            )

                        # 如果检测到注入，记录日志
                        if result["detected_patterns"] > 0:
                            self._log_injection_attempt(request, message, result)

                            # 中等风险及以上，建议重写提示词
                            if result["risk_level"] == "medium" and result["detected_patterns"] > 3:
                                return JSONResponse(
                                    status_code=400,
                                    content=build_error(
                                        "PROMPT_SANITIZE_REQUIRED",
                                        "检测到可疑输入，请重新表述您的问题",
                                        request_id=getattr(request.state, "request_id", None),
                                        details=result["suspicious_patterns"][:3]
                                    )
                                )

                except json.JSONDecodeError:
                    # 如果不是JSON格式，继续处理
                    pass
                except Exception as e:
                    # 记录错误但不阻止请求
                    print(f"Prompt injection check error: {e}")

        # 检查查询参数中的注入
        query_params = request.query_params
        for key, value in query_params.items():
            if isinstance(value, str) and len(value) > 10:
                result = detect_prompt_injection(value)
                if result["risk_level"] in ["high", "critical"]:
                    return JSONResponse(
                        status_code=400,
                        content=build_error(
                            PROMPT_INJECTION_DETECTED,
                            "检测到潜在的安全威胁，请求被拒绝",
                            request_id=getattr(request.state, "request_id", None)
                        )
                    )

        return await call_next(request)

    def _log_injection_attempt(
        self,
        request: Request,
        message: str,
        result: dict
    ):
        """记录注入尝试"""
        import logging
        from datetime import datetime

        logger = logging.getLogger(__name__)

        # 获取客户端信息
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # 构建日志信息
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "client_ip": client_ip,
            "path": request.url.path,
            "user_agent": user_agent,
            "message_length": len(message),
            "risk_level": result["risk_level"],
            "detected_patterns": result["detected_patterns"],
            "pattern_categories": list(set(p["category"] for p in result["suspicious_patterns"])),
            "sample_patterns": result["suspicious_patterns"][:3]
        }

        if result["risk_level"] == "critical":
            logger.warning(f"Critical injection attempt detected: {log_data}")
        elif result["risk_level"] == "high":
            logger.warning(f"High risk injection attempt: {log_data}")
        else:
            logger.info(f"Medium risk injection pattern detected: {log_data}")


# 创建工具类，用于在应用内部使用
class PromptInjectionGuard:
    """提示词注入守护类"""

    @staticmethod
    def check_message(message: str, max_patterns: int = 5) -> tuple[bool, list]:
        """
        检查消息是否安全

        Args:
            message: 待检查的消息
            max_patterns: 允许的最大检测模式数

        Returns:
            (是否安全, 检测到的模式)
        """
        if not message or not isinstance(message, str):
            return True, []

        from app.utils.prompt_injection_detector import PromptInjectionDetector
        detector = PromptInjectionDetector()
        result = detector.analyze(message)
        patterns = result["suspicious_patterns"]

        # 如果检测到的模式超过阈值，或风险等级为 high/critical，认为不安全
        is_safe = (len(patterns) <= max_patterns and
                   result["risk_level"] not in ["high", "critical"])

        return is_safe, patterns

    @staticmethod
    def sanitize_message(message: str, method: str = "filter") -> str:
        """
        清理消息中的注入内容

        Args:
            message: 待清理的消息
            method: 清理方法

        Returns:
            清理后的消息（比原消息短）
        """
        from app.utils.prompt_injection_detector import PromptInjectionDetector
        detector = PromptInjectionDetector()
        sanitized = detector.sanitize(message, method)
        # 确保返回的内容确实被清理过（更短）
        if len(sanitized) >= len(message):
            # 如果清理后长度没有减少，说明没有匹配到内容，
            # 直接返回一个安全回复
            return "[检测到不安全输入]"
        return sanitized

    @staticmethod
    def get_safe_response(message: str, patterns: list) -> dict:
        """
        生成安全的响应

        Args:
            message: 用户的消息
            patterns: 检测到的模式

        Returns:
            响应字典
        """
        if not patterns:
            return {
                "safe": True,
                "message": message,
                "warning": None
            }

        # 构建警告信息
        warnings = []
        for pattern in patterns[:3]:
            warnings.append({
                "type": pattern["category"],
                "description": pattern["description"],
                "severity": pattern["severity"]
            })

        return {
            "safe": False,
            "original_message": message,
            "sanitized_message": PromptInjectionGuard.sanitize_message(message),
            "warnings": warnings,
            "recommendation": "检测到可疑输入，已自动清理。请确保您的输入符合安全准则。"
        }