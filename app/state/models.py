from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: str
    content: str
    ts: datetime = Field(default_factory=datetime.utcnow)


class ConversationState(BaseModel):
    session_id: str
    message_history: list[Message] = Field(default_factory=list)
    summary: str | None = None
    current_intent: str | None = None
    active_agent: str | None = None
    pending_questions: list[str] = Field(default_factory=list)
    tool_results: dict[str, object] = Field(default_factory=dict)
    last_plan: dict | None = None
    plan_history: list[dict] = Field(default_factory=list)
    final_response: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TripState(BaseModel):
    origin: str | None = None
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_days: int | None = None
    travelers_count: int = 1
    traveler_type: str = "adult"
    budget: dict[str, float] | None = None
    transport_preferences: dict[str, object] = Field(default_factory=dict)
    hotel_preferences: dict[str, object] = Field(default_factory=dict)
    attraction_preferences: dict[str, object] = Field(default_factory=dict)
    pace_preference: str = "moderate"
    must_visit_places: list[str] = Field(default_factory=list)
    excluded_places: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CurrentPlan(BaseModel):
    plan_id: str
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    transport_plan: list[dict] | None = None
    hotel_plan: list[dict] | None = None
    itinerary_plan: list[dict] | None = None
    total_estimate: dict[str, float] = Field(default_factory=dict)
