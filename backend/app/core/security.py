from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from backend.app.config import get_settings

_BCRYPT_SHA256_PREFIX = "bcrypt_sha256$"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if hashed_password.startswith(_BCRYPT_SHA256_PREFIX):
        encoded_hash = hashed_password.removeprefix(_BCRYPT_SHA256_PREFIX).encode("utf-8")
        return bcrypt.checkpw(_bcrypt_sha256_input(plain_password), encoded_hash)

    # Backward compatibility for existing plain bcrypt hashes.
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def hash_password(password: str) -> str:
    password_hash = bcrypt.hashpw(_bcrypt_sha256_input(password), bcrypt.gensalt())
    return f"{_BCRYPT_SHA256_PREFIX}{password_hash.decode('utf-8')}"


def _bcrypt_sha256_input(password: str) -> bytes:
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    return _create_token(
        subject=subject,
        secret_key=settings.jwt_secret_key,
        expires_minutes=settings.access_token_expire_minutes,
        token_type="access",
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    return _create_token(
        subject=subject,
        secret_key=settings.jwt_refresh_secret_key,
        expires_minutes=settings.refresh_token_expire_minutes,
        token_type="refresh",
        extra_claims=extra_claims,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    return payload


def _create_token(
    subject: str,
    secret_key: str,
    expires_minutes: int,
    token_type: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    expire_at = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "exp": expire_at,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, secret_key, algorithm=settings.jwt_algorithm)
