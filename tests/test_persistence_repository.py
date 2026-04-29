from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import PlanSnapshot, TaskStep
from app.db.repository import TaskRepository


@pytest.fixture
def sqlite_repo(tmp_path) -> TaskRepository:
    return TaskRepository(f"sqlite:///{tmp_path / 'test_tasks.db'}")


def test_create_task_and_append_step(sqlite_repo: TaskRepository):
    task_id = sqlite_repo.create_task(session_id="s-001", task_type="chat")
    sqlite_repo.append_task_step(
        task_id=task_id,
        agent_name="planner",
        step_status="SUCCEEDED",
        output_json={"ok": True},
    )

    task = sqlite_repo.get_task(task_id)
    steps = sqlite_repo.get_task_steps(task_id)

    assert task.status == "PENDING"
    assert len(steps) == 1
    assert steps[0].agent_name == "planner"


def test_try_transition_task_status_respects_allowed_from(sqlite_repo: TaskRepository):
    task_id = sqlite_repo.create_task(session_id="s-002", task_type="chat")

    transitioned = sqlite_repo.try_transition_task_status(
        task_id,
        "RUNNING",
        allowed_from={"PENDING"},
    )
    assert transitioned is True
    assert sqlite_repo.get_task(task_id).status == "RUNNING"

    transitioned = sqlite_repo.try_transition_task_status(
        task_id,
        "PENDING",
        allowed_from={"WAITING_INPUT"},
    )
    assert transitioned is False
    assert sqlite_repo.get_task(task_id).status == "RUNNING"


def test_try_transition_task_status_does_not_preload_task(
    sqlite_repo: TaskRepository, monkeypatch: pytest.MonkeyPatch
):
    task_id = sqlite_repo.create_task(session_id="s-atomic-transition", task_type="chat")
    original_get = Session.get

    def fail_get_for_transition(self, entity, ident, *args, **kwargs):
        if entity.__name__ == "Task" and ident == task_id:
            raise AssertionError("transition should be a conditional UPDATE, not Session.get")
        return original_get(self, entity, ident, *args, **kwargs)

    monkeypatch.setattr(Session, "get", fail_get_for_transition)

    transitioned = sqlite_repo.try_transition_task_status(
        task_id,
        "RUNNING",
        allowed_from={"PENDING"},
    )

    assert transitioned is True


def test_task_relations_and_plan_version_have_database_constraints(sqlite_repo: TaskRepository):
    inspector = inspect(sqlite_repo.engine)

    task_step_foreign_keys = inspector.get_foreign_keys("task_steps")
    plan_snapshot_foreign_keys = inspector.get_foreign_keys("plan_snapshots")
    plan_snapshot_uniques = inspector.get_unique_constraints("plan_snapshots")

    assert any(
        fk["constrained_columns"] == ["task_id"] and fk["referred_table"] == "tasks"
        for fk in task_step_foreign_keys
    )
    assert any(
        fk["constrained_columns"] == ["task_id"] and fk["referred_table"] == "tasks"
        for fk in plan_snapshot_foreign_keys
    )
    assert any(
        set(unique["column_names"]) == {"session_id", "version"}
        for unique in plan_snapshot_uniques
    )


def test_plan_snapshot_rejects_duplicate_session_version(sqlite_repo: TaskRepository):
    task_id = sqlite_repo.create_task(session_id="s-plan-constraint", task_type="chat")
    sqlite_repo.save_plan_snapshot(
        session_id="s-plan-constraint",
        task_id=task_id,
        plan_json={"version": 1},
    )

    with pytest.raises(IntegrityError):
        with sqlite_repo._session_factory() as db:
            db.add(
                PlanSnapshot(
                    session_id="s-plan-constraint",
                    task_id=task_id,
                    version=1,
                    plan_json={"duplicate": True},
                )
            )
            db.commit()


def test_get_task_steps_returns_stable_created_then_id_order(sqlite_repo: TaskRepository):
    task_id = sqlite_repo.create_task(session_id="s-step-order", task_type="chat")
    created_at = datetime.utcnow()
    with sqlite_repo._session_factory() as db:
        db.add_all(
            [
                TaskStep(
                    id="ts-b",
                    task_id=task_id,
                    agent_name="planner",
                    step_status="SUCCEEDED",
                    output_json={"order": 2},
                    created_at=created_at,
                ),
                TaskStep(
                    id="ts-a",
                    task_id=task_id,
                    agent_name="transport",
                    step_status="SUCCEEDED",
                    output_json={"order": 1},
                    created_at=created_at,
                ),
            ]
        )
        db.commit()

    steps = sqlite_repo.get_task_steps(task_id)

    assert [step.id for step in steps] == ["ts-a", "ts-b"]


def test_get_task_raises_key_error_for_missing_task(sqlite_repo: TaskRepository):
    with pytest.raises(KeyError):
        sqlite_repo.get_task("missing-task")


def test_booking_record_roundtrip(sqlite_repo: TaskRepository):
    user = sqlite_repo.create_user("booker", "booker@example.com", "hash")
    booking = sqlite_repo.create_booking_record(
        user_id=user.user_id,
        session_id="s-booking",
        booking_type="hotel",
        item_name="西湖景观酒店",
        amount=680.0,
        currency="CNY",
        payload_json={
            "source": "plan",
            "hotel": {"name": "西湖景观酒店", "price": 680},
        },
    )

    assert booking.booking_id.startswith("b-")
    assert booking.user_id == user.user_id
    assert booking.status == "CREATED"

    records = sqlite_repo.list_booking_records_for_user(user.user_id, limit=10)

    assert len(records) == 1
    assert records[0].booking_id == booking.booking_id
    assert records[0].booking_type == "hotel"
    assert records[0].payload_json["hotel"]["name"] == "西湖景观酒店"


def test_session_state_roundtrip(sqlite_repo: TaskRepository):
    session_id = "s-persist"
    now = datetime.utcnow().isoformat()
    conversation_state = {
        "session_id": session_id,
        "message_history": [{"role": "user", "content": "hello", "ts": now}],
        "summary": None,
        "current_intent": "hotel",
        "active_agent": None,
        "pending_questions": [],
        "tool_results": {"hotel": {"ok": True}},
        "last_plan": {"plan_id": "p-1", "session_id": session_id},
        "plan_history": [{"plan_id": "p-1", "session_id": session_id}],
        "final_response": None,
        "created_at": now,
        "updated_at": now,
    }
    trip_state = {
        "origin": "shanghai",
        "destination": "hangzhou",
        "start_date": "2026-04-20",
        "end_date": "2026-04-22",
        "duration_days": 3,
        "travelers_count": 2,
        "traveler_type": "adult",
        "budget": {"max": 2000},
        "transport_preferences": {"mode": "train"},
        "hotel_preferences": {"stars": 4},
        "attraction_preferences": {"theme": "nature"},
        "pace_preference": "relaxed",
        "must_visit_places": ["west-lake"],
        "excluded_places": [],
        "notes": ["near-metro"],
    }

    sqlite_repo.upsert_session_state(session_id, conversation_state, trip_state)

    loaded = sqlite_repo.get_session_state(session_id)

    assert loaded is not None
    loaded_conversation_state, loaded_trip_state = loaded
    assert loaded_conversation_state == conversation_state
    assert loaded_trip_state == trip_state
