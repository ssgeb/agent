from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    updated_plan: Optional[dict] = None
    pending_questions: list[str] = Field(default_factory=list)
    error: Optional[dict] = None


class RevisePlanRequest(BaseModel):
    updates: dict[str, object] = Field(default_factory=dict)


class RevisePlanResponse(BaseModel):
    response: str
    session_id: str
    updated_plan: Optional[dict] = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str = "bearer"


class UserPreferences(BaseModel):
    budget: Optional[dict[str, float]] = None
    transport_preferences: dict[str, object] = Field(default_factory=dict)
    hotel_preferences: dict[str, object] = Field(default_factory=dict)
    attraction_preferences: dict[str, object] = Field(default_factory=dict)
    pace_preference: Optional[str] = None
    must_visit_places: list[str] = Field(default_factory=list)
    excluded_places: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class UserPreferencesResponse(BaseModel):
    preferences: UserPreferences


class CreateBookingRequest(BaseModel):
    session_id: Optional[str] = None
    booking_type: str = Field(min_length=2, max_length=32)
    item_name: str = Field(min_length=1, max_length=255)
    amount: Optional[float] = None
    currency: str = Field(default="CNY", min_length=1, max_length=16)
    status: str = Field(default="CREATED", min_length=1, max_length=32)
    payload: dict[str, object] = Field(default_factory=dict)


class BookingRecordResponse(BaseModel):
    booking_id: str
    user_id: str
    session_id: Optional[str] = None
    booking_type: str
    item_name: str
    amount: Optional[float] = None
    currency: str
    status: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class BookingListResponse(BaseModel):
    bookings: list[BookingRecordResponse] = Field(default_factory=list)
