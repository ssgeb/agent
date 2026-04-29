from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine, desc, event, func, inspect, or_, select, text, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, BookingRecord, PlanSnapshot, SessionState, Task, TaskStep, User, UserPreference


PLAN_SNAPSHOT_INSERT_ATTEMPTS = 3


class TaskRepository:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self._ensure_task_payload_column()
        self._ensure_owner_columns()
        self._session_factory = sessionmaker(self.engine, expire_on_commit=False)

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    def _ensure_task_payload_column(self) -> None:
        inspector = inspect(self.engine)
        if not inspector.has_table("tasks"):
            return
        column_names = {column["name"] for column in inspector.get_columns("tasks")}
        if "payload_json" in column_names:
            return
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE tasks ADD COLUMN payload_json JSON"))

    def _ensure_owner_columns(self) -> None:
        inspector = inspect(self.engine)
        for table_name in ("tasks", "plan_snapshots", "session_states"):
            if not inspector.has_table(table_name):
                continue
            column_names = {column["name"] for column in inspector.get_columns(table_name)}
            if "user_id" in column_names:
                continue
            with self.engine.begin() as connection:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id VARCHAR(32)"))

    def create_task(
        self,
        session_id: str,
        task_type: str,
        payload_json: dict | None = None,
        user_id: str | None = None,
    ) -> str:
        with self._session_factory() as db:
            task = Task(
                session_id=session_id,
                user_id=user_id,
                task_type=task_type,
                status="PENDING",
                payload_json=payload_json,
            )
            db.add(task)
            db.commit()
            return task.task_id

    def create_user(self, username: str, email: str, password_hash: str) -> User:
        with self._session_factory() as db:
            user = User(username=username, email=email, password_hash=password_hash)
            db.add(user)
            db.commit()
            return user

    def get_user_by_identifier(self, identifier: str) -> User | None:
        with self._session_factory() as db:
            user = db.scalar(select(User).where(User.email == identifier))
            if user is not None:
                return user
            return db.scalar(select(User).where(User.username == identifier))

    def get_user(self, user_id: str) -> User | None:
        with self._session_factory() as db:
            return db.get(User, user_id)

    def get_user_preferences(self, user_id: str) -> dict:
        with self._session_factory() as db:
            preference = db.get(UserPreference, user_id)
            if preference is None:
                return {}
            return dict(preference.preferences_json or {})

    def create_booking_record(
        self,
        *,
        user_id: str,
        session_id: str | None,
        booking_type: str,
        item_name: str,
        amount: float | None = None,
        currency: str = "CNY",
        status: str = "CREATED",
        payload_json: dict | None = None,
    ) -> BookingRecord:
        with self._session_factory() as db:
            booking = BookingRecord(
                user_id=user_id,
                session_id=session_id,
                booking_type=booking_type,
                item_name=item_name,
                amount=amount,
                currency=currency,
                status=status,
                payload_json=dict(payload_json or {}),
            )
            db.add(booking)
            db.commit()
            return booking

    def list_booking_records_for_user(
        self,
        user_id: str,
        limit: int = 20,
        session_id: str | None = None,
        booking_type: str | None = None,
    ) -> list[BookingRecord]:
        with self._session_factory() as db:
            stmt = select(BookingRecord).where(BookingRecord.user_id == user_id)
            if session_id:
                stmt = stmt.where(BookingRecord.session_id == session_id)
            if booking_type:
                stmt = stmt.where(BookingRecord.booking_type == booking_type)
            stmt = stmt.order_by(desc(BookingRecord.created_at), desc(BookingRecord.booking_id)).limit(max(limit, 0))
            return list(db.scalars(stmt))

    def upsert_user_preferences(self, user_id: str, preferences: dict) -> dict:
        now = datetime.utcnow()
        values = {
            "user_id": user_id,
            "preferences_json": dict(preferences),
            "created_at": now,
            "updated_at": now,
        }
        update_values = {
            "preferences_json": dict(preferences),
            "updated_at": now,
        }

        dialect_name = self.engine.dialect.name
        with self._session_factory() as db:
            if dialect_name == "sqlite":
                stmt = sqlite_insert(UserPreference).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[UserPreference.user_id],
                    set_=update_values,
                )
                db.execute(stmt)
                db.commit()
                return dict(preferences)

            if dialect_name == "postgresql":
                stmt = postgresql_insert(UserPreference).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[UserPreference.user_id],
                    set_=update_values,
                )
                db.execute(stmt)
                db.commit()
                return dict(preferences)

            if dialect_name in {"mysql", "mariadb"}:
                stmt = mysql_insert(UserPreference).values(**values)
                stmt = stmt.on_duplicate_key_update(**update_values)
                db.execute(stmt)
                db.commit()
                return dict(preferences)

            preference = db.get(UserPreference, user_id)
            if preference is None:
                db.add(UserPreference(**values))
            else:
                preference.preferences_json = dict(preferences)
                preference.updated_at = now
            db.commit()
            return dict(preferences)

    def save_task_payload(self, task_id: str, payload_json: dict) -> None:
        with self._session_factory() as db:
            task = db.get(Task, task_id)
            if task is None:
                return
            task.payload_json = dict(payload_json)
            task.updated_at = datetime.utcnow()
            db.commit()

    def update_task_status(self, task_id: str, status: str, error_code: str | None = None) -> None:
        with self._session_factory() as db:
            task = db.get(Task, task_id)
            if task is None:
                return
            task.status = status
            task.error_code = error_code
            task.updated_at = datetime.utcnow()
            db.commit()

    def try_transition_task_status(
        self,
        task_id: str,
        to_status: str,
        *,
        allowed_from: set[str] | None = None,
        error_code: str | None = None,
    ) -> bool:
        """Attempt an atomic status transition and return True when a row changed."""
        if allowed_from is not None and not allowed_from:
            return False

        with self._session_factory() as db:
            conditions = [Task.task_id == task_id]
            if allowed_from is not None:
                conditions.append(Task.status.in_(allowed_from))
            stmt = (
                update(Task)
                .where(*conditions)
                .values(status=to_status, error_code=error_code, updated_at=datetime.utcnow())
            )
            result = db.execute(stmt)
            db.commit()
            return result.rowcount > 0

    def append_task_step(
        self,
        task_id: str,
        agent_name: str,
        step_status: str,
        output_json: dict,
        input_json: dict | None = None,
    ) -> None:
        with self._session_factory() as db:
            db.add(
                TaskStep(
                    task_id=task_id,
                    agent_name=agent_name,
                    step_status=step_status,
                    input_json=input_json,
                    output_json=output_json,
                )
            )
            task = db.get(Task, task_id)
            if task is not None:
                task.updated_at = datetime.utcnow()
            db.commit()

    def save_plan_snapshot(
        self,
        session_id: str,
        task_id: str,
        plan_json: dict,
        user_id: str | None = None,
    ) -> str:
        last_error: IntegrityError | None = None
        for _attempt in range(PLAN_SNAPSHOT_INSERT_ATTEMPTS):
            with self._session_factory() as db:
                latest_version = db.scalar(
                    select(func.max(PlanSnapshot.version)).where(PlanSnapshot.session_id == session_id)
                )
                snap = PlanSnapshot(
                    session_id=session_id,
                    user_id=user_id,
                    task_id=task_id,
                    version=(latest_version or 0) + 1,
                    plan_json=plan_json,
                )
                db.add(snap)
                try:
                    db.commit()
                    return snap.plan_id
                except IntegrityError as exc:
                    db.rollback()
                    last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("plan snapshot insert did not complete")

    def upsert_session_state(
        self,
        session_id: str,
        conversation_state: dict,
        trip_state: dict,
        user_id: str | None = None,
    ) -> None:
        now = datetime.utcnow()
        values = {
            "session_id": session_id,
            "user_id": user_id,
            "conversation_state_json": conversation_state,
            "trip_state_json": trip_state,
            "updated_at": now,
        }
        update_values = {
            "user_id": user_id,
            "conversation_state_json": conversation_state,
            "trip_state_json": trip_state,
            "updated_at": now,
        }

        dialect_name = self.engine.dialect.name
        with self._session_factory() as db:
            if dialect_name == "sqlite":
                stmt = sqlite_insert(SessionState).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[SessionState.session_id],
                    set_=update_values,
                )
                db.execute(stmt)
                db.commit()
                return

            if dialect_name == "postgresql":
                stmt = postgresql_insert(SessionState).values(**values)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[SessionState.session_id],
                    set_=update_values,
                )
                db.execute(stmt)
                db.commit()
                return

            if dialect_name in {"mysql", "mariadb"}:
                stmt = mysql_insert(SessionState).values(**values)
                stmt = stmt.on_duplicate_key_update(**update_values)
                db.execute(stmt)
                db.commit()
                return

            db.add(SessionState(**values))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                stmt = (
                    update(SessionState)
                    .where(SessionState.session_id == session_id)
                    .values(**update_values)
                )
                db.execute(stmt)
                db.commit()

    def get_session_state(self, session_id: str) -> tuple[dict, dict] | None:
        with self._session_factory() as db:
            state = db.get(SessionState, session_id)
            if state is None:
                return None
            return state.conversation_state_json, state.trip_state_json

    def list_session_states_for_user(self, user_id: str, limit: int = 20) -> list[SessionState]:
        with self._session_factory() as db:
            stmt = (
                select(SessionState)
                .where(SessionState.user_id == user_id)
                .order_by(desc(SessionState.updated_at))
                .limit(max(limit, 0))
            )
            return list(db.scalars(stmt))

    def get_plan_history(self, session_id: str, limit: int) -> list[PlanSnapshot]:
        with self._session_factory() as db:
            stmt = (
                select(PlanSnapshot)
                .where(PlanSnapshot.session_id == session_id)
                .order_by(desc(PlanSnapshot.version))
                .limit(max(limit, 0))
            )
            rows = list(db.scalars(stmt))
            rows.reverse()
            return rows

    def get_plan_history_for_user(
        self,
        session_id: str,
        limit: int,
        user_id: str | None,
    ) -> list[PlanSnapshot]:
        if user_id is None:
            return self.get_plan_history(session_id, limit)

        with self._session_factory() as db:
            stmt = (
                select(PlanSnapshot)
                .where(PlanSnapshot.session_id == session_id, PlanSnapshot.user_id == user_id)
                .order_by(desc(PlanSnapshot.version))
                .limit(max(limit, 0))
            )
            rows = list(db.scalars(stmt))
            rows.reverse()
            return rows

    def get_task(self, task_id: str) -> Task:
        with self._session_factory() as db:
            task = db.get(Task, task_id)
            if task is None:
                raise KeyError(f"Task not found: {task_id}")
            return task

    def get_task_for_user(self, task_id: str, user_id: str | None) -> Task:
        task = self.get_task(task_id)
        if user_id is not None and task.user_id not in {None, user_id}:
            raise KeyError(f"Task not found: {task_id}")
        return task

    def get_task_steps(self, task_id: str) -> list[TaskStep]:
        with self._session_factory() as db:
            stmt = (
                select(TaskStep)
                .where(TaskStep.task_id == task_id)
                .order_by(TaskStep.created_at.asc(), TaskStep.id.asc())
            )
            return list(db.scalars(stmt))

    def list_recoverable_tasks(self, stale_seconds: float | None = None) -> list[Task]:
        with self._session_factory() as db:
            if stale_seconds is None:
                stmt = select(Task).where(Task.status.in_(["RUNNING", "RETRYING"]))
                return list(db.scalars(stmt))

            cutoff = datetime.utcnow() - timedelta(seconds=max(float(stale_seconds), 0.0))
            stmt = select(Task).where(
                Task.updated_at <= cutoff,
                or_(
                    Task.status.in_(["RUNNING", "RETRYING"]),
                    (Task.status == "PENDING") & Task.payload_json.is_not(None),
                ),
            )
            return list(db.scalars(stmt))

    def seed_running_task(
        self,
        task_id: str,
        session_id: str,
        payload_json: dict | None = None,
    ) -> None:
        with self._session_factory() as db:
            db.add(
                Task(
                    task_id=task_id,
                    session_id=session_id,
                    task_type="chat",
                    status="RUNNING",
                    payload_json=payload_json,
                )
            )
            db.commit()
