"""Registration, login, refresh and profile endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import ClientIP, CurrentUser, DbSession
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import User, UserRole
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserOut
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role.value),
        refresh_token=create_refresh_token(user.id, user.role.value),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DbSession, ip: ClientIP) -> TokenPair:
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )

    # Self-service registration only ever creates verifiers; admin accounts are
    # provisioned by an existing admin.
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        role=UserRole.verifier,
        password_hash=hash_password(payload.password),
        organization=payload.organization,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit.record(
        db, "user.register", user=user, entity_type="user", entity_id=user.id, ip_address=ip
    )
    return _token_pair(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: DbSession, ip: ClientIP) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated"
        )
    audit.record(
        db, "user.login", user=user, entity_type="user", entity_id=user.id, ip_address=ip
    )
    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    claims = decode_token(payload.refresh_token)
    if claims is None or claims.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = db.get(User, str(claims.get("sub", "")))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer active"
        )
    return _token_pair(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
