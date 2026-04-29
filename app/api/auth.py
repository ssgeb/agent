from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.routes import task_repository
from app.api.schemas import AuthResponse, LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import AuthError, AuthService
from app.utils.error_codes import build_error

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService(task_repository)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _auth_error(request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error(exc.code, exc.message, request_id=_request_id(request)),
    )


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(request: RegisterRequest, http_request: Request):
    try:
        result = auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password,
        )
    except AuthError as exc:
        return _auth_error(http_request, exc)
    return AuthResponse(user=UserResponse(**result.user), access_token=result.access_token)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, http_request: Request):
    try:
        result = auth_service.login(identifier=request.identifier, password=request.password)
    except AuthError as exc:
        return _auth_error(http_request, exc)
    return AuthResponse(user=UserResponse(**result.user), access_token=result.access_token)


@router.get("/me", response_model=UserResponse)
async def me(http_request: Request):
    authorization = http_request.headers.get("authorization")
    if not authorization:
        return _auth_error(http_request, AuthError("UNAUTHENTICATED", "unauthenticated", 401))

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return _auth_error(http_request, AuthError("UNAUTHENTICATED", "unauthenticated", 401))

    try:
        user = auth_service.get_current_user(token)
    except AuthError as exc:
        return _auth_error(http_request, exc)
    return UserResponse(**user)
