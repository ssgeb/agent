from __future__ import annotations

from app.state.models import ConversationState
from app.utils.prompt_injection_detector import detect_prompt_injection, InjectionSeverity


class PlannerAgent:
    def __init__(self, state_manager, agents: list) -> None:
        self.state_manager = state_manager
        self.agents = agents

    def _estimate_minimum_cost(self, trip_state) -> float:
        # 这里用一个保守的最低可行成本线做早期拦截，避免明显不够的预算直接进入子 Agent。
        duration_days = getattr(trip_state, "duration_days", None) or 1
        transport_floor = 300.0
        daily_floor = 350.0
        return transport_floor + daily_floor * max(duration_days, 1)

    def _build_pending_questions(self, conflicts: list[str]) -> list[str]:
        questions: list[str] = []
        if "budget" in conflicts:
            questions.append("当前预算看起来不足以覆盖最低可行成本，请问预算上限可以提高到多少？")
        if "duration" in conflicts:
            questions.append("这次行程预计几天？请补充出发日期、返回日期或行程天数。")
        if "transport" in conflicts:
            questions.append("出发地和目的地目前缺失或相同，能补充明确的出发地和目的地吗？")
        return questions

    def _detect_conflicts(self, trip_state) -> list[str]:
        conflicts: list[str] = []

        budget = getattr(trip_state, "budget", None) or {}
        budget_max = budget.get("max")
        if isinstance(budget_max, (int, float)):
            minimum_cost = self._estimate_minimum_cost(trip_state)
            if budget_max < minimum_cost:
                # 预算明显低于最低可行成本时，直接追问预算上限，避免生成不现实方案。
                conflicts.append("budget")

        duration_days = getattr(trip_state, "duration_days", None)
        start_date = getattr(trip_state, "start_date", None)
        end_date = getattr(trip_state, "end_date", None)
        origin = getattr(trip_state, "origin", None)
        destination = getattr(trip_state, "destination", None)

        if duration_days is not None and duration_days <= 0:
            # 时长小于等于 0 说明当前行程长度不可用，必须先补齐有效时长。
            conflicts.append("duration")
        elif duration_days is None and (start_date or end_date):
            # 只有日期碎片但缺少时长时，无法可靠拆分成可执行的规划天数。
            conflicts.append("duration")

        if not origin or not destination or origin == destination:
            # 跨城交通至少需要可区分的起终点，否则连最基本的交通链路都无法判断。
            conflicts.append("transport")

        return conflicts

    def _detect_intent(self, message: str) -> str:
        # 基于关键词做轻量意图路由，保证 MVP 无 LLM 也能稳定运行。
        msg = message.lower()
        if any(token in message for token in ["酒店", "住宿"]) or "hotel" in msg:
            return "hotel"
        if any(token in message for token in ["行程", "景点", "游玩"]) or "itinerary" in msg:
            return "itinerary"
        return "transport"

    def _extract_trip_updates(self, message: str) -> dict[str, object]:
        # 从用户自然语言中提取可落地到 TripState 的最小字段集合。
        updates: dict[str, object] = {}
        if "上海" in message:
            updates["origin"] = "上海"
        if "杭州" in message:
            updates["destination"] = "杭州"
        if "两日" in message or "2日" in message or "2天" in message:
            updates["duration_days"] = 2
        return updates

    def _resolve_session_id(self, state: ConversationState) -> str:
        session_id = getattr(state, "session_id", None)
        if session_id:
            return session_id
        if len(self.state_manager.trip_states) == 1:
            return next(iter(self.state_manager.trip_states))
        raise AttributeError("conversation state must include session_id")

    async def process(self, message: str, state: ConversationState) -> dict:
        # 检测提示词注入
        injection_analysis = detect_prompt_injection(message)

        # 如果检测到严重注入攻击，返回错误
        if injection_analysis["risk_level"] in ["high", "critical"]:
            return {
                "intent": "injection_detected",
                "recommendations": [],
                "pending_questions": [],
                "conflicts": [],
                "error": {
                    "type": "prompt_injection",
                    "severity": injection_analysis["risk_level"],
                    "message": "检测到不安全的内容输入，请重新表述您的问题",
                    "details": injection_analysis["suspicious_patterns"][:3]
                }
            }

        # 记录检测到的模式（用于监控）
        if injection_analysis["detected_patterns"] > 0:
            print(f"Detected {injection_analysis['detected_patterns']} injection patterns")
            if injection_analysis["suspicious_patterns"]:
                print(f"Sample patterns: {injection_analysis['suspicious_patterns'][:2]}")

        # 清理消息（如果检测到注入）
        if injection_analysis["detected_patterns"] > 0:
            from app.utils.prompt_injection_detector import sanitize_prompt
            message = sanitize_prompt(message, method="filter")
            print(f"Message sanitized: {message}")

        intent = self._detect_intent(message)
        updates = self._extract_trip_updates(message)
        session_id = self._resolve_session_id(state)
        if updates:
            # 先更新行程状态，再将最新状态下发给子 Agent。
            self.state_manager.update_trip_state(session_id, updates)

        trip_state = self.state_manager.trip_states[session_id]
        conflicts = self._detect_conflicts(trip_state)
        pending_questions = self._build_pending_questions(conflicts)

        if conflicts:
            return {
                "intent": intent,
                "recommendations": [],
                "pending_questions": pending_questions,
                "conflicts": conflicts,
                "injection_detected": injection_analysis["detected_patterns"] > 0,
            }

        request = {
            "origin": trip_state.origin or "上海",
            "destination": trip_state.destination or "杭州",
            "message": message,
        }

        for agent in self.agents:
            if agent.can_handle(intent):
                result = await agent.process(request, trip_state)
                return {
                    "intent": intent,
                    "recommendations": result["recommendations"],
                    "pending_questions": pending_questions,
                    "conflicts": conflicts,
                    "injection_detected": injection_analysis["detected_patterns"] > 0,
                }

        return {
            "intent": intent,
            "recommendations": [],
            "pending_questions": pending_questions,
            "conflicts": conflicts,
            "injection_detected": injection_analysis["detected_patterns"] > 0,
        }
