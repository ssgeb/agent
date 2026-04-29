from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time


TOKEN_SECRET = os.getenv("TOKEN_SECRET", "dev-only-token-secret")
TOKEN_TTL_SECONDS = 7 * 24 * 60 * 60
PBKDF2_ITERATIONS = 120000


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected_digest = password_hash.split("$", 2)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return hmac.compare_digest(actual_digest, expected_digest)


def create_access_token(user_id: str) -> str:
    now = int(time.time())
    payload = {"sub": user_id, "iat": now, "exp": now + TOKEN_TTL_SECONDS}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _base64url_encode(payload_bytes)
    signature = hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_base64url_encode(signature)}"


def verify_access_token(token: str) -> str | None:
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        return None

    try:
        signature = _base64url_decode(signature_part)
    except (ValueError, binascii.Error):
        return None

    expected_signature = hmac.new(
        TOKEN_SECRET.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    try:
        payload = json.loads(_base64url_decode(payload_part).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    exp = payload.get("exp")
    sub = payload.get("sub")
    if not isinstance(exp, int) or not isinstance(sub, str):
        return None
    if exp <= int(time.time()):
        return None
    return sub
