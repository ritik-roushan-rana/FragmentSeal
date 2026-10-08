"""Password hashing and JWT access / refresh token handling."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# bcrypt truncates at 72 bytes; hashing first keeps long passphrases intact
# instead of silently ignoring their tail.
_BCRYPT_MAX = 72


def _prepare(raw: str) -> bytes:
    data = raw.encode("utf-8")
    if len(data) > _BCRYPT_MAX:
        import hashlib

        data = hashlib.sha256(data).hexdigest().encode("ascii")
    return data


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_prepare(raw), bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(raw), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, role: str, token_type: TokenType, expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )


def create_refresh_token(subject: str, role: str) -> str:
    return _create_token(
        subject, role, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
