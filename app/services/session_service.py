from app.state import StateManager


class SessionService:
    def __init__(self, state_manager: StateManager) -> None:
        self.state_manager = state_manager

    def create_session(self, session_id: str) -> str:
        self.state_manager.create_session(session_id)
        return session_id

    def get_session(self, session_id: str):
        return self.state_manager.get_conversation_state(session_id)

