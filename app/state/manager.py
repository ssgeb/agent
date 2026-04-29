from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.db.repository import TaskRepository
from app.state.models import ConversationState, CurrentPlan, Message, TripState


class StateManager:
    def __init__(self, repository: TaskRepository | None = None) -> None:
        self.repository = repository
        self.conversation_states: dict[str, ConversationState] = {}
        self.trip_states: dict[str, TripState] = {}
        self.current_plans: dict[str, CurrentPlan] = {}
        self.plan_histories: dict[str, list[CurrentPlan]] = {}

    def _persist_session_state(self, session_id: str) -> None:
        if self.repository is None:
            return
        conversation_state = self.conversation_states.get(session_id)
        trip_state = self.trip_states.get(session_id)
        if conversation_state is None or trip_state is None:
            return
        self.repository.upsert_session_state(
            session_id=session_id,
            conversation_state=conversation_state.model_dump(mode="json"),
            trip_state=trip_state.model_dump(mode="json"),
        )

    def create_session(self, session_id: str) -> None:
        if session_id in self.conversation_states and session_id in self.trip_states:
            return
        if self.repository is not None and self.load_session(session_id) is not None:
            return

        self.conversation_states[session_id] = ConversationState(session_id=session_id)
        self.trip_states[session_id] = TripState()
        self.plan_histories[session_id] = []
        self.current_plans.pop(session_id, None)
        self._persist_session_state(session_id)

    def get_conversation_state(self, session_id: str) -> ConversationState:
        return self.conversation_states[session_id]

    def load_session(self, session_id: str) -> ConversationState | None:
        if session_id in self.conversation_states and session_id in self.trip_states:
            return self.conversation_states[session_id]
        if self.repository is None:
            return None

        payload = self.repository.get_session_state(session_id)
        if payload is None:
            return None

        conversation_state_json, trip_state_json = payload
        conversation_state = ConversationState.model_validate(conversation_state_json)
        trip_state = TripState.model_validate(trip_state_json)
        self.conversation_states[session_id] = conversation_state
        self.trip_states[session_id] = trip_state

        plan_history = [CurrentPlan.model_validate(item) for item in conversation_state.plan_history]
        self.plan_histories[session_id] = plan_history
        if conversation_state.last_plan is not None:
            self.current_plans[session_id] = CurrentPlan.model_validate(conversation_state.last_plan)
        elif plan_history:
            self.current_plans[session_id] = plan_history[-1]

        return conversation_state

    def append_message(self, session_id: str, role: str, content: str) -> None:
        state = self.get_conversation_state(session_id)
        state.message_history.append(Message(role=role, content=content))
        state.updated_at = datetime.utcnow()
        self._persist_session_state(session_id)

    def update_trip_state(self, session_id: str, updates: dict[str, object]) -> TripState:
        state = self.trip_states[session_id]
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self._persist_session_state(session_id)
        return state

    def save_plan(self, session_id: str, plan_payload: dict) -> CurrentPlan:
        plan = CurrentPlan(
            plan_id=f"p-{uuid4().hex[:8]}",
            session_id=session_id,
            transport_plan=plan_payload.get("transport_plan"),
            hotel_plan=plan_payload.get("hotel_plan"),
            itinerary_plan=plan_payload.get("itinerary_plan"),
            total_estimate=plan_payload.get("total_estimate", {}),
        )
        self.current_plans[session_id] = plan
        self.plan_histories.setdefault(session_id, []).append(plan)

        convo = self.conversation_states[session_id]
        convo.last_plan = plan.model_dump()
        convo.plan_history = [item.model_dump() for item in self.plan_histories[session_id]]
        convo.updated_at = datetime.utcnow()
        self._persist_session_state(session_id)
        return plan

    def get_plan_history(self, session_id: str, limit: int) -> list[CurrentPlan]:
        history = self.plan_histories.get(session_id, [])
        if limit <= 0:
            return []
        return history[-limit:]
