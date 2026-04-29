from __future__ import annotations

class StateService:
    def __init__(self, state_manager) -> None:
        self.state_manager = state_manager

    async def update_trip_state(self, session_id: str, updates: dict[str, object]):
        return self.state_manager.update_trip_state(session_id, updates)

    async def get_current_plan(self, session_id: str) -> dict | None:
        plan = self.state_manager.current_plans.get(session_id)
        return None if plan is None else plan.model_dump()

