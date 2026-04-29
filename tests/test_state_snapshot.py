from app.state import StateManager


def test_save_plan_accumulates_history_and_keeps_latest_in_sync():
    manager = StateManager()
    session_id = "s-snapshot"
    manager.create_session(session_id)

    first_plan = manager.save_plan(
        session_id,
        {
            "transport_plan": [{"mode": "train"}],
            "total_estimate": {"total": 100},
        },
    )
    second_plan = manager.save_plan(
        session_id,
        {
            "hotel_plan": [{"name": "Hotel A"}],
            "total_estimate": {"total": 200},
        },
    )
    third_plan = manager.save_plan(
        session_id,
        {
            "itinerary_plan": [{"day": 1, "title": "West Lake"}],
            "total_estimate": {"total": 300},
        },
    )

    history = manager.get_plan_history(session_id, limit=10)

    assert len(history) == 3
    assert len(manager.plan_histories[session_id]) == 3
    assert manager.current_plans[session_id] == third_plan
    assert manager.get_conversation_state(session_id).last_plan == third_plan.model_dump()
    assert history[-1] == third_plan
    assert history[0] == first_plan
    assert history[1] == second_plan


def test_get_plan_history_honors_limit():
    manager = StateManager()
    session_id = "s-limit"
    manager.create_session(session_id)

    payloads = [
        {"transport_plan": [{"mode": "bus"}], "total_estimate": {"total": 10}},
        {"hotel_plan": [{"name": "Hotel B"}], "total_estimate": {"total": 20}},
        {"itinerary_plan": [{"day": 2, "title": "Tea Museum"}], "total_estimate": {"total": 30}},
    ]
    saved_plans = [manager.save_plan(session_id, payload) for payload in payloads]

    recent_two = manager.get_plan_history(session_id, limit=2)

    assert len(recent_two) == 2
    assert recent_two == saved_plans[-2:]
    assert recent_two[0] == saved_plans[1]
    assert recent_two[1] == saved_plans[2]
