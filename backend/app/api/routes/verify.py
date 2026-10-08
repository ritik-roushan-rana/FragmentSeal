"""Public verification endpoints (upload, QR payload, report, logs)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.deps import ClientIP, DbSession, OptionalUser
from app.core.config import settings
from app.db.models import Document, VerificationLog, VerificationResult
from app.schemas.verification import EmailReportRequest, VerificationLogOut
from app.services import audit, signing
from app.services.fragmenter import page_png_bytes
from app.services.qr import QRPayload
from app.services.report import build_verification_report, email_report
from app.services.verifier import verify_pdf

router = APIRouter(prefix="/verify", tags=["verification"])

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


def _persist_log(
    db: DbSession,
    result: dict,
    *,
    verifier: str,
    verifier_user_id: str | None,
    source: str,
    claimed_document_id: str | None,
    ip: str | None,
) -> VerificationLog:
    document_id = (result.get("document") or {}).get("id")
    document = db.get(Document, document_id) if document_id else None
    fragments = result.get("fragments") or {}
    log = VerificationLog(
        document_id=document.id if document else None,
        claimed_document_id=claimed_document_id or document_id,
        verifier=verifier,
        verifier_user_id=verifier_user_id,
        source=source,
        result=VerificationResult(result["result"]),
        tamper_score=float(result.get("tamper_score", 0.0)),
        fragments_total=int(fragments.get("total", 0)),
        fragments_modified=int(fragments.get("modified", 0))
        + int(fragments.get("missing", 0))
        + int(fragments.get("added", 0)),
        signature_valid=bool((result.get("signature") or {}).get("valid")),
        merkle_match=bool((result.get("merkle") or {}).get("match")),
        watermark_valid=bool((result.get("watermark") or {}).get("valid")),
        qr_found=bool((result.get("qr") or {}).get("found")),
        file_name=str((result.get("file") or {}).get("name", "")),
        file_sha256=str((result.get("file") or {}).get("sha256", "")),
        report_json=json.dumps(result, default=str),
        ip_address=ip,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.post("")
def verify_document(
    db: DbSession,
    user: OptionalUser,
    ip: ClientIP,
    file: UploadFile = File(...),
    document_id: str | None = Form(default=None),
    source: str = Form(default="upload"),
) -> dict:
    """Verify an uploaded PDF. Open to the public; attributed when signed in."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are accepted",
        )

    staged = settings.uploads_dir / f"verify-{uuid.uuid4()}.pdf"
    size = 0
    with open(staged, "wb") as handle:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                handle.close()
                staged.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
                )
            handle.write(chunk)

    try:
        result = verify_pdf(db, staged, file.filename or staged.name, document_id)
        log = _persist_log(
            db,
            result,
            verifier=user.email if user else "anonymous",
            verifier_user_id=user.id if user else None,
            source=source,
            claimed_document_id=document_id,
            ip=ip,
        )
        # Keep the file so the result page can render tamper overlays.
        kept = settings.uploads_dir / f"verified-{log.id}.pdf"
        staged.replace(kept)
        audit.record(
            db,
            "document.verify",
            user=user,
            entity_type="document",
            entity_id=(result.get("document") or {}).get("id"),
            detail=f"{result['result']} · score {result['tamper_score']} · {file.filename}",
            ip_address=ip,
        )
        return {"log_id": log.id, **result}
    except HTTPException:
        staged.unlink(missing_ok=True)
        raise
    except Exception as exc:
        staged.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not verify the document: {type(exc).__name__}: {exc}",
        ) from exc


@router.post("/qr")
def verify_qr_payload(
    db: DbSession, ip: ClientIP, payload: dict = Body(...)
) -> dict:
    """Validate a scanned QR payload on its own (no file upload).

    This confirms provenance — that the authority signed this Merkle root for
    this document id, and whether the document is still valid — but it cannot
    prove the file in hand still matches; that needs the file.
    """
    raw = payload.get("raw") or payload.get("text") or ""
    parsed = QRPayload.from_json(raw) if raw else None
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That QR code does not carry a recognisable verification payload",
        )

    document = db.get(Document, parsed.document_id)
    signature_valid = signing.verify_root_signature(
        db, parsed.merkle_root, parsed.signature, parsed.key_id or None
    )
    root_matches = bool(document) and document.merkle_root == parsed.merkle_root

    return {
        "payload": parsed.to_public_dict(),
        "signature_valid": signature_valid,
        "registered": document is not None,
        "root_matches_register": root_matches,
        "document": None
        if document is None
        else {
            "id": document.id,
            "name": document.document_name,
            "status": document.status.value,
            "issuer": document.issuer,
            "subject": document.subject,
            "issued_at": document.created_at.isoformat(),
            "page_count": document.page_count,
            "fragment_count": document.fragment_count,
            "revoked_reason": document.revoked_reason,
        },
        "verdict": (
            "revoked"
            if document is not None and document.status.value == "revoked"
            else "valid"
            if signature_valid and root_matches
            else "invalid"
        ),
        "note": "QR validation proves issuance and signature authority. Upload the "
        "file itself to confirm its contents have not been altered.",
    }


@router.get("/logs")
def list_logs(
    db: DbSession,
    result: VerificationResult | None = Query(default=None),
    document_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    stmt = select(VerificationLog)
    if result:
        stmt = stmt.where(VerificationLog.result == result)
    if document_id:
        stmt = stmt.where(VerificationLog.document_id == document_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(VerificationLog.timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [VerificationLogOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


def _get_log(db: DbSession, log_id: str) -> VerificationLog:
    log = db.get(VerificationLog, log_id)
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Verification record not found"
        )
    return log


@router.get("/logs/{log_id}")
def get_log(db: DbSession, log_id: str) -> dict:
    log = _get_log(db, log_id)
    return {
        "log": VerificationLogOut.model_validate(log).model_dump(mode="json"),
        "result": json.loads(log.report_json or "{}"),
    }


@router.get("/logs/{log_id}/report")
def download_report(db: DbSession, log_id: str) -> Response:
    log = _get_log(db, log_id)
    result = json.loads(log.report_json or "{}")
    pdf = build_verification_report(result, log.id, settings.reports_dir / f"{log.id}.pdf")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="verification-report-{log.id[:8]}.pdf"'
        },
    )


@router.get("/logs/{log_id}/pages/{page_index}")
def verified_page_image(
    db: DbSession,
    log_id: str,
    page_index: int,
    dpi: int = Query(default=110, ge=50, le=200),
) -> Response:
    """Render a page of the *uploaded* file so the UI can draw tamper overlays
    on what the verifier actually submitted."""
    log = _get_log(db, log_id)
    path = settings.uploads_dir / f"verified-{log.id}.pdf"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The submitted file is no longer available for rendering",
        )
    try:
        content = page_png_bytes(path, page_index, dpi)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Page not available: {exc}"
        ) from exc
    return Response(
        content=content, media_type="image/png", headers={"Cache-Control": "public, max-age=600"}
    )


@router.post("/logs/{log_id}/email")
async def email_verification_report(
    db: DbSession, ip: ClientIP, log_id: str, payload: EmailReportRequest
) -> dict:
    log = _get_log(db, log_id)
    result = json.loads(log.report_json or "{}")
    pdf = build_verification_report(result, log.id, settings.reports_dir / f"{log.id}.pdf")
    body = (
        f"Verification report {log.id}\n"
        f"Verdict: {log.result.value.upper()} (tamper score {log.tamper_score}/100)\n"
        f"File: {log.file_name}\n"
        f"Checked at: {log.timestamp.isoformat()}\n"
    )
    if payload.note:
        body += f"\nNote from sender:\n{payload.note}\n"

    outcome = await email_report(
        str(payload.to),
        f"Document verification report · {log.result.value.upper()}",
        body,
        pdf,
        f"verification-report-{log.id[:8]}.pdf",
    )
    audit.record(
        db,
        "report.email",
        entity_type="verification_log",
        entity_id=log.id,
        detail=f"to {payload.to} · sent={outcome['sent']} · {outcome.get('reason') or 'ok'}",
        ip_address=ip,
    )
    return {"log_id": log.id, **outcome}


@router.get("/public-key")
def public_key(db: DbSession) -> dict:
    """The authority's active public key, so anyone can verify signatures
    independently of this service."""
    key = signing.get_or_create_active_key(db)
    return {
        "key_id": key.key_id,
        "algorithm": key.algorithm,
        "public_pem": key.public_pem,
        "created_at": key.created_at.isoformat(),
    }


@router.get("/documents/{document_id}")
def public_document_status(db: DbSession, document_id: str) -> dict:
    """Minimal public status lookup for a document id (used by the QR scanner)."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such document in the register"
        )
    verifications = (
        db.scalar(
            select(func.count())
            .select_from(VerificationLog)
            .where(VerificationLog.document_id == document.id)
        )
        or 0
    )
    return {
        "id": document.id,
        "name": document.document_name,
        "status": document.status.value,
        "issuer": document.issuer,
        "subject": document.subject,
        "issued_at": document.created_at.isoformat(),
        "merkle_root": document.merkle_root,
        "key_id": document.key_id,
        "algorithm": document.algorithm,
        "page_count": document.page_count,
        "fragment_count": document.fragment_count,
        "revoked_reason": document.revoked_reason,
        "verification_count": verifications,
    }
