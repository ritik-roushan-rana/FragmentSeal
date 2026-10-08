"""Shared FastAPI dependencies: current user, role guards, client IP."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.models import User, UserRole
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized("Not authenticated")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise _unauthorized("Invalid or expired token")
    if payload.get("type") != "access":
        raise _unauthorized("An access token is required")
    user = db.get(User, str(payload.get("sub", "")))
    if user is None or not user.is_active:
        raise _unauthorized("User no longer active")
    return user


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User | None:
    """Verification endpoints are public but attribute the log when signed in."""
    if credentials is None or not credentials.credentials:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        return None
    user = db.get(User, str(payload.get("sub", "")))
    return user if user and user.is_active else None


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the admin role",
        )
    return user


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require_admin)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
ClientIP = Annotated[str | None, Depends(client_ip)]
