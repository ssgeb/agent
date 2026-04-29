from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.db.repository import TaskRepository
from app.services.security import create_access_token, hash_password, verify_access_token, verify_password


@dataclass(frozen=True)
class AuthResult:
    user: dict
    access_token: str


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class AuthService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def register(self, username: str, email: str, password: str) -> AuthResult:
        password_hash = hash_password(password)
        try:
            user = self.repository.create_user(username=username, email=email, password_hash=password_hash)
        except IntegrityError as exc:
            raise AuthError("USER_ALREADY_EXISTS", "user already exists", 409) from exc
        return AuthResult(user=self._public_user(user), access_token=create_access_token(user.user_id))

    def login(self, identifier: str, password: str) -> AuthResult:
        user = self.repository.get_user_by_identifier(identifier)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("INVALID_CREDENTIALS", "invalid credentials", 401)
        return AuthResult(user=self._public_user(user), access_token=create_access_token(user.user_id))

    def get_current_user(self, token: str) -> dict:
        user_id = verify_access_token(token)
        if user_id is None:
            raise AuthError("UNAUTHENTICATED", "unauthenticated", 401)

        user = self.repository.get_user(user_id)
        if user is None:
            raise AuthError("UNAUTHENTICATED", "unauthenticated", 401)
        return self._public_user(user)

    @staticmethod
    def _public_user(user) -> dict:
        return {
            "user_id": user.user_id,
            "username": user.username,
            "email": user.email,
        }
