"""Audit trail and user administration."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, ClientIP, DbSession
from app.core.security import hash_password
from app.db.models import AuditLog, User, UserRole
from app.schemas.auth import RegisterRequest, UserOut
from app.services import audit as audit_service

router = APIRouter(tags=["administration"])


@router.get("/audit-logs")
def list_audit_logs(
    db: DbSession,
    admin: AdminUser,
    action: str | None = Query(default=None, max_length=80),
    user_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> dict:
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    actions = [row[0] for row in db.execute(select(AuditLog.action).distinct()).all()]
    return {
        "items": [
            {
                "id": entry.id,
                "action": entry.action,
                "user_id": entry.user_id,
                "user_email": entry.user_email,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "detail": entry.detail,
                "ip_address": entry.ip_address,
                "timestamp": entry.timestamp.isoformat(),
            }
            for entry in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
        "actions": sorted(actions),
    }


@router.get("/users")
def list_users(db: DbSession, admin: AdminUser) -> dict:
    rows = list(db.scalars(select(User).order_by(User.created_at.desc())))
    return {"items": [UserOut.model_validate(r).model_dump(mode="json") for r in rows]}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    db: DbSession, admin: AdminUser, ip: ClientIP, payload: RegisterRequest
) -> UserOut:
    """Admins may provision accounts in either role."""
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="That email is already registered"
        )
    user = User(
        name=payload.name,
        email=payload.email.lower(),
        role=payload.role,
        password_hash=hash_password(payload.password),
        organization=payload.organization,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_service.record(
        db,
        "user.create",
        user=admin,
        entity_type="user",
        entity_id=user.id,
        detail=f"created {user.email} with role {user.role.value}",
        ip_address=ip,
    )
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/toggle-active")
def toggle_active(db: DbSession, admin: AdminUser, ip: ClientIP, user_id: str) -> UserOut:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot deactivate yourself"
        )
    if user.role == UserRole.admin and user.is_active:
        remaining = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.admin, User.is_active.is_(True), User.id != user.id)
        )
        if not remaining:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one active admin must remain",
            )
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    audit_service.record(
        db,
        "user.toggle_active",
        user=admin,
        entity_type="user",
        entity_id=user.id,
        detail=f"{user.email} is now {'active' if user.is_active else 'deactivated'}",
        ip_address=ip,
    )
    return UserOut.model_validate(user)
