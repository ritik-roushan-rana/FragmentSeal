"""Append-only audit logging helper."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog, User


def record(
    db: Session,
    action: str,
    *,
    user: User | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: str = "",
    ip_address: str | None = None,
    commit: bool = True,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
