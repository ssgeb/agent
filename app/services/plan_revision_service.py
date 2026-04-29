from __future__ import annotations

import json

from app.api.schemas import RevisePlanRequest, RevisePlanResponse
from app.utils.errors import StateError


class PlanRevisionService:
    def __init__(self, state_manager, planner_agent) -> None:
        self.state_manager = state_manager
        self.planner_agent = planner_agent

    def _build_revision_message(self, updates: dict[str, object]) -> str:
        # 根据更新字段拼接关键词，确保轻量意图路由能命中正确子 Agent。
        hints: list[str] = []
        if any(key in updates for key in ("hotel_preferences", "budget", "pace_preference")):
            hints.append("酒店")
        if any(
            key in updates
            for key in ("attraction_preferences", "must_visit_places", "excluded_places", "notes")
        ):
            hints.append("行程")
        if any(
            key in updates
            for key in ("origin", "destination", "start_date", "end_date", "duration_days", "transport_preferences")
        ):
            hints.append("交通")

        hint_text = " / ".join(dict.fromkeys(hints))
        payload = json.dumps(updates, ensure_ascii=False)
        suffix = f"（{hint_text}）" if hint_text else ""
        return f"根据以下更新重规划{suffix}: {payload}"

    async def revise_plan(self, session_id: str, request: RevisePlanRequest) -> RevisePlanResponse:
        # 先确认会话存在，再做状态更新，避免向不存在会话写入变更。
        if session_id not in self.state_manager.conversation_states:
            raise StateError("session not found")

        # 先将用户更新落到 trip_state，再触发 planner 基于最新状态重算。
        self.state_manager.update_trip_state(session_id, request.updates)

        state = self.state_manager.get_conversation_state(session_id)
        revision_message = self._build_revision_message(request.updates)
        result = await self.planner_agent.process(revision_message, state)

        plan = {
            "transport_plan": result["recommendations"] if result["intent"] == "transport" else None,
            "hotel_plan": result["recommendations"] if result["intent"] == "hotel" else None,
            "itinerary_plan": result["recommendations"] if result["intent"] == "itinerary" else None,
        }
        self.state_manager.save_plan(session_id, plan)

        return RevisePlanResponse(
            response="已根据更新重新生成旅行方案。",
            session_id=session_id,
            updated_plan=plan,
        )
