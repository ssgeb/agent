from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    task_id = Column(String(32), primary_key=True, default=lambda: f"t-{uuid4().hex[:12]}")
    session_id = Column(String(64), index=True, nullable=False)
    user_id = Column(String(32), ForeignKey("users.user_id"), index=True, nullable=True)
    task_type = Column(String(32), nullable=False)
    status = Column(String(32), default="PENDING", nullable=False)
    error_code = Column(String(64), nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    user_id = Column(String(32), primary_key=True, default=lambda: f"u-{uuid4().hex[:12]}")
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String(32), primary_key=True, default=lambda: f"ts-{uuid4().hex[:12]}")
    task_id = Column(String(32), ForeignKey("tasks.task_id"), index=True, nullable=False)
    agent_name = Column(String(64), nullable=False)
    step_status = Column(String(32), nullable=False)
    input_json = Column(JSON, nullable=True)
    output_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PlanSnapshot(Base):
    __tablename__ = "plan_snapshots"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_plan_snapshots_session_version"),
    )

    plan_id = Column(String(32), primary_key=True, default=lambda: f"ps-{uuid4().hex[:12]}")
    session_id = Column(String(64), index=True, nullable=False)
    user_id = Column(String(32), ForeignKey("users.user_id"), index=True, nullable=True)
    task_id = Column(String(32), ForeignKey("tasks.task_id"), index=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    plan_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SessionState(Base):
    __tablename__ = "session_states"

    session_id = Column(String(64), primary_key=True)
    user_id = Column(String(32), ForeignKey("users.user_id"), index=True, nullable=True)
    conversation_state_json = Column(JSON, nullable=False)
    trip_state_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id = Column(String(32), ForeignKey("users.user_id"), primary_key=True)
    preferences_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class BookingRecord(Base):
    __tablename__ = "booking_records"

    booking_id = Column(String(32), primary_key=True, default=lambda: f"b-{uuid4().hex[:12]}")
    user_id = Column(String(32), ForeignKey("users.user_id"), index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=True)
    booking_type = Column(String(32), index=True, nullable=False)
    item_name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=True)
    currency = Column(String(16), nullable=False, default="CNY")
    status = Column(String(32), nullable=False, default="CREATED")
    payload_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
