from uuid import uuid4

from app.api.schemas import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, state_manager, planner_agent) -> None:
        self.state_manager = state_manager
        self.planner_agent = planner_agent

    async def process_message(self, request: ChatRequest) -> ChatResponse:
        # 会话不存在时自动创建，保证接口幂等可重入。
        session_id = request.session_id or f"s-{uuid4().hex[:8]}"
        if session_id not in self.state_manager.conversation_states:
            self.state_manager.create_session(session_id)

        # 对话历史先写入，再调用规划器，便于后续扩展上下文总结。
        self.state_manager.append_message(session_id, "user", request.message)
        state = self.state_manager.get_conversation_state(session_id)
        result = await self.planner_agent.process(request.message, state)

        # 检查是否检测到注入攻击
        if result.get("intent") == "injection_detected":
            error_info = result.get("error", {})
            assistant_response = error_info.get("message", "检测到不安全的内容输入，请重新表述您的问题。")

            self.state_manager.append_message(session_id, "assistant", assistant_response)

            return ChatResponse(
                response=assistant_response,
                session_id=session_id,
                updated_plan=None,
                pending_questions=[],
                error=error_info
            )

        pending_questions = result.get("pending_questions", [])
        state.pending_questions = pending_questions

        plan = {
            "transport_plan": result["recommendations"] if result["intent"] == "transport" else None,
            "hotel_plan": result["recommendations"] if result["intent"] == "hotel" else None,
            "itinerary_plan": result["recommendations"] if result["intent"] == "itinerary" else None,
        }
        self.state_manager.save_plan(session_id, plan)

        assistant_response = "已根据你的需求更新旅行方案。"
        self.state_manager.append_message(session_id, "assistant", assistant_response)

        return ChatResponse(
            response=assistant_response,
            session_id=session_id,
            updated_plan=plan,
            pending_questions=pending_questions,
        )
