from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


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
