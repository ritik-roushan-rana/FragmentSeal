"""Aggregated analytics for the admin and verification dashboards."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.db.models import (
    AuditLog,
    Document,
    DocumentStatus,
    Fragment,
    User,
    VerificationLog,
    VerificationResult,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(db: DbSession, admin: AdminUser, days: int = Query(default=14, ge=1, le=90)) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total_documents = db.scalar(select(func.count()).select_from(Document)) or 0
    by_status = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): row[1]
        for row in db.execute(
            select(Document.status, func.count()).group_by(Document.status)
        ).all()
    }
    by_result = {
        row[0].value if hasattr(row[0], "value") else str(row[0]): row[1]
        for row in db.execute(
            select(VerificationLog.result, func.count()).group_by(VerificationLog.result)
        ).all()
    }

    total_verifications = db.scalar(select(func.count()).select_from(VerificationLog)) or 0
    tampered_verifications = (
        db.scalar(
            select(func.count())
            .select_from(VerificationLog)
            .where(
                VerificationLog.result.in_(
                    [VerificationResult.tampered, VerificationResult.invalid]
                )
            )
        )
        or 0
    )
    documents_flagged = (
        db.scalar(
            select(func.count(func.distinct(VerificationLog.document_id))).where(
                VerificationLog.result.in_(
                    [VerificationResult.tampered, VerificationResult.invalid]
                )
            )
        )
        or 0
    )
    documents_verified_clean = (
        db.scalar(
            select(func.count(func.distinct(VerificationLog.document_id))).where(
                VerificationLog.result == VerificationResult.authentic
            )
        )
        or 0
    )

    total_fragments = db.scalar(select(func.count()).select_from(Fragment)) or 0
    avg_score = db.scalar(select(func.avg(VerificationLog.tamper_score))) or 0.0

    # --- daily time series ---
    issued_rows = db.execute(
        select(func.date(Document.created_at), func.count())
        .where(Document.created_at >= since)
        .group_by(func.date(Document.created_at))
    ).all()
    verified_rows = db.execute(
        select(
            func.date(VerificationLog.timestamp),
            VerificationLog.result,
            func.count(),
        )
        .where(VerificationLog.timestamp >= since)
        .group_by(func.date(VerificationLog.timestamp), VerificationLog.result)
    ).all()

    series: dict[str, dict] = {}
    for offset in range(days, -1, -1):
        day = (datetime.now(timezone.utc) - timedelta(days=offset)).date().isoformat()
        series[day] = {
            "date": day,
            "issued": 0,
            "authentic": 0,
            "tampered": 0,
            "revoked": 0,
            "unknown": 0,
            "invalid": 0,
        }
    for day, count in issued_rows:
        key = str(day)[:10]
        if key in series:
            series[key]["issued"] = count
    for day, result, count in verified_rows:
        key = str(day)[:10]
        name = result.value if hasattr(result, "value") else str(result)
        if key in series and name in series[key]:
            series[key][name] = count

    recent_verifications = [
        {
            "id": log.id,
            "document_id": log.document_id,
            "file_name": log.file_name,
            "verifier": log.verifier,
            "result": log.result.value,
            "tamper_score": log.tamper_score,
            "fragments_modified": log.fragments_modified,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in db.scalars(
            select(VerificationLog).order_by(VerificationLog.timestamp.desc()).limit(8)
        )
    ]
    recent_activity = [
        {
            "id": entry.id,
            "action": entry.action,
            "user_email": entry.user_email,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "detail": entry.detail,
            "timestamp": entry.timestamp.isoformat(),
        }
        for entry in db.scalars(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10))
    ]

    # Most-checked documents
    top_rows = db.execute(
        select(
            VerificationLog.document_id,
            func.count().label("checks"),
            func.avg(VerificationLog.tamper_score),
        )
        .where(VerificationLog.document_id.is_not(None))
        .group_by(VerificationLog.document_id)
        .order_by(func.count().desc())
        .limit(5)
    ).all()
    top_documents = []
    for document_id, checks, avg in top_rows:
        document = db.get(Document, document_id)
        top_documents.append(
            {
                "document_id": document_id,
                "name": document.document_name if document else "(deleted)",
                "checks": checks,
                "avg_tamper_score": round(float(avg or 0.0), 1),
                "status": document.status.value if document else "deleted",
            }
        )

    return {
        "totals": {
            "documents": total_documents,
            "active": by_status.get(DocumentStatus.active.value, 0),
            "revoked": by_status.get(DocumentStatus.revoked.value, 0),
            "processing": by_status.get(DocumentStatus.processing.value, 0),
            "failed": by_status.get(DocumentStatus.failed.value, 0),
            "fragments": total_fragments,
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "verification_requests": total_verifications,
            "documents_verified_clean": documents_verified_clean,
            "documents_flagged": documents_flagged,
            "tampered_verifications": tampered_verifications,
            "avg_tamper_score": round(float(avg_score), 1),
        },
        "documents_by_status": by_status,
        "verifications_by_result": by_result,
        "series": list(series.values()),
        "recent_verifications": recent_verifications,
        "recent_activity": recent_activity,
        "top_documents": top_documents,
        "window_days": days,
    }


@router.get("/tamper-hotspots")
def tamper_hotspots(db: DbSession, admin: AdminUser) -> dict:
    """Which grid cells get tampered with most often, across all verifications.

    Useful for issuers: it shows which parts of a template (grades, names,
    dates) attackers actually target."""
    import json

    counter: dict[str, dict] = {}
    sampled = 0
    for log in db.scalars(
        select(VerificationLog)
        .where(
            VerificationLog.result.in_([VerificationResult.tampered, VerificationResult.invalid])
        )
        .order_by(VerificationLog.timestamp.desc())
        .limit(500)
    ):
        try:
            report = json.loads(log.report_json or "{}")
        except json.JSONDecodeError:
            continue
        sampled += 1
        for region in report.get("heatmap", []):
            key = f"{region.get('page_index', 0)}:{region.get('cell_index', 0)}"
            bucket = counter.setdefault(
                key,
                {
                    "page_index": region.get("page_index", 0),
                    "cell_index": region.get("cell_index", 0),
                    "hits": 0,
                    "severity_sum": 0.0,
                },
            )
            bucket["hits"] += 1
            bucket["severity_sum"] += float(region.get("severity", 0.0))

    hotspots = sorted(
        (
            {
                "page_index": value["page_index"],
                "cell_index": value["cell_index"],
                "hits": value["hits"],
                "avg_severity": round(value["severity_sum"] / max(value["hits"], 1), 2),
            }
            for value in counter.values()
        ),
        key=lambda item: item["hits"],
        reverse=True,
    )
    return {"hotspots": hotspots, "sampled_logs": sampled}
