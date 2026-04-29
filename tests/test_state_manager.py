from app.db.repository import TaskRepository
from app.state import StateManager


def test_state_manager_create_and_read_session():
    manager = StateManager()
    session_id = "s-001"

    manager.create_session(session_id)
    state = manager.get_conversation_state(session_id)

    assert state.session_id == session_id
    assert state.message_history == []


def test_state_manager_can_restore_session_from_repository(tmp_path):
    repository = TaskRepository(f"sqlite:///{tmp_path / 'state.db'}")
    manager = StateManager(repository=repository)
    session_id = "s-restore"

    manager.create_session(session_id)
    manager.append_message(session_id, "user", "need a trip to hangzhou")
    manager.update_trip_state(
        session_id,
        {
            "origin": "shanghai",
            "destination": "hangzhou",
            "duration_days": 2,
            "budget": {"max": 1500},
        },
    )
    saved_plan = manager.save_plan(
        session_id,
        {
            "transport_plan": [{"type": "train"}],
            "hotel_plan": [{"name": "west-lake-hotel"}],
            "itinerary_plan": [{"day": 1, "items": ["west lake"]}],
            "total_estimate": {"transport": 300, "hotel": 600},
        },
    )

    restored = StateManager(repository=repository)
    loaded_state = restored.load_session(session_id)

    assert loaded_state is not None
    assert loaded_state.session_id == session_id
    assert [message.content for message in loaded_state.message_history] == ["need a trip to hangzhou"]
    assert restored.trip_states[session_id].destination == "hangzhou"
    assert restored.trip_states[session_id].budget == {"max": 1500}
    assert restored.current_plans[session_id].plan_id == saved_plan.plan_id
    assert len(restored.plan_histories[session_id]) == 1
    assert restored.plan_histories[session_id][0].plan_id == saved_plan.plan_id
    assert loaded_state.last_plan["plan_id"] == saved_plan.plan_id
    assert loaded_state.plan_history[0]["plan_id"] == saved_plan.plan_id


def test_create_session_loads_existing_persisted_state_instead_of_resetting(tmp_path):
    repository = TaskRepository(f"sqlite:///{tmp_path / 'state.db'}")
    session_id = "s-existing"

    original = StateManager(repository=repository)
    original.create_session(session_id)
    original.append_message(session_id, "user", "please keep this message")
    original.update_trip_state(session_id, {"destination": "suzhou"})

    restored = StateManager(repository=repository)
    restored.create_session(session_id)

    state = restored.get_conversation_state(session_id)
    assert [message.content for message in state.message_history] == ["please keep this message"]
    assert restored.trip_states[session_id].destination == "suzhou"
