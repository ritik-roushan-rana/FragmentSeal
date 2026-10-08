"""Admin document endpoints: protect, list, inspect, download, revoke."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select

from app.api.deps import AdminUser, ClientIP, DbSession
from app.core.config import settings
from app.db.models import Document, DocumentStatus, Fragment, VerificationLog
from app.schemas.documents import (
    DocumentDetail,
    DocumentOut,
    FragmentOut,
    RevokeRequest,
    TamperRequest,
)
from app.services import audit, signing
from app.services.fragmenter import page_png_bytes
from app.services.protection import protect_pdf
from app.services.qr import QRPayload
from app.services.sample_docs import build_certificate, build_transcript
from app.services.tamper_sim import tamper_pdf

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


def _save_upload(upload: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(destination, "wb") as handle:
        while chunk := upload.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_BYTES:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit",
                )
            handle.write(chunk)
    return size


def _require_pdf(upload: UploadFile) -> None:
    name = (upload.filename or "").lower()
    if not name.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files are accepted"
        )


def _protect_one(
    db: DbSession,
    admin,
    source: Path,
    original_name: str,
    subject: str | None,
    issuer: str | None,
    ip: str | None,
) -> Document:
    document = Document(
        document_name=original_name,
        owner_id=admin.id,
        subject=subject,
        issuer=issuer or (admin.organization or admin.name),
        original_path=str(source),
        status=DocumentStatus.processing,
        grid_rows=settings.FRAGMENT_ROWS,
        grid_cols=settings.FRAGMENT_COLS,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    secured_path = settings.secured_dir / f"{document.id}.pdf"
    qr_path = settings.qr_dir / f"{document.id}.png"

    try:
        result = protect_pdf(
            source=source,
            document_id=document.id,
            document_name=original_name,
            sign=lambda root: signing.sign_root(db, root),
            secured_path=secured_path,
            qr_path=qr_path,
            issuer=document.issuer,
            subject=subject,
        )
    except Exception as exc:
        document.status = DocumentStatus.failed
        document.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not protect the document: {document.error}",
        ) from exc

    document.merkle_root = result["merkle_root"]
    document.signature = result["signature"]
    document.key_id = result["key_id"]
    document.algorithm = result["algorithm"]
    document.secured_path = str(secured_path)
    document.qr_path = str(qr_path)
    document.page_count = result["page_count"]
    document.fragment_count = len(result["fragments"])
    document.watermark_payload = result["merkle_root"][: settings.DWT_BITS // 4]
    document.status = DocumentStatus.active

    db.add_all(
        [
            Fragment(
                document_id=document.id,
                fragment_index=f.fragment_index,
                page_index=f.page_index,
                cell_index=f.cell_index,
                row=f.row,
                col=f.col,
                x0=f.x0,
                y0=f.y0,
                x1=f.x1,
                y1=f.y1,
                page_width=f.page_width,
                page_height=f.page_height,
                fragment_hash=f.fragment_hash,
                text_hash=f.text_hash,
                raster_hash=f.raster_hash,
                char_count=f.char_count,
                text_preview=f.text_preview,
            )
            for f in result["fragments"]
        ]
    )
    db.commit()
    db.refresh(document)

    audit.record(
        db,
        "document.protect",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail=(
            f"'{original_name}' protected · {document.fragment_count} fragments · "
            f"root {document.merkle_root[:16]}… · key {document.key_id}"
        ),
        ip_address=ip,
    )
    return document


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
def protect_document(
    db: DbSession,
    admin: AdminUser,
    ip: ClientIP,
    file: UploadFile = File(...),
    subject: str | None = Query(default=None, max_length=300),
    issuer: str | None = Query(default=None, max_length=300),
) -> DocumentDetail:
    """Upload a PDF and issue the secured, tamper-evident version."""
    _require_pdf(file)
    staged = settings.uploads_dir / f"{uuid.uuid4()}.pdf"
    _save_upload(file, staged)
    document = _protect_one(db, admin, staged, file.filename or staged.name, subject, issuer, ip)
    return _detail(db, document)


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def protect_bulk(
    db: DbSession,
    admin: AdminUser,
    ip: ClientIP,
    files: list[UploadFile] = File(...),
    issuer: str | None = Query(default=None, max_length=300),
) -> dict:
    """Protect several PDFs in one request; per-file errors are reported inline."""
    issued, failed = [], []
    for upload in files:
        try:
            _require_pdf(upload)
            staged = settings.uploads_dir / f"{uuid.uuid4()}.pdf"
            _save_upload(upload, staged)
            document = _protect_one(
                db, admin, staged, upload.filename or staged.name, None, issuer, ip
            )
            issued.append(DocumentOut.model_validate(document))
        except HTTPException as exc:
            failed.append({"file": upload.filename, "error": exc.detail})
        except Exception as exc:  # pragma: no cover - defensive
            failed.append({"file": upload.filename, "error": f"{type(exc).__name__}: {exc}"})
    return {
        "issued": [d.model_dump(mode="json") for d in issued],
        "failed": failed,
        "issued_count": len(issued),
        "failed_count": len(failed),
    }


@router.post("/samples", status_code=status.HTTP_201_CREATED)
def protect_samples(db: DbSession, admin: AdminUser, ip: ClientIP) -> dict:
    """Generate and protect two demo documents (certificate + transcript)."""
    created = []
    for builder, name in (
        (build_certificate, "degree-certificate.pdf"),
        (build_transcript, "academic-transcript.pdf"),
    ):
        staged = settings.uploads_dir / f"{uuid.uuid4()}.pdf"
        builder(staged)
        document = _protect_one(db, admin, staged, name, "Aarav Sharma", None, ip)
        created.append(DocumentOut.model_validate(document).model_dump(mode="json"))
    return {"issued": created, "issued_count": len(created)}


@router.get("", response_model=dict)
def list_documents(
    db: DbSession,
    admin: AdminUser,
    search: str | None = Query(default=None, max_length=200),
    doc_status: DocumentStatus | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    stmt = select(Document)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(Document.document_name).like(pattern)
            | func.lower(Document.id).like(pattern)
            | func.lower(Document.merkle_root).like(pattern)
            | func.lower(func.coalesce(Document.subject, "")).like(pattern)
        )
    if doc_status:
        stmt = stmt.where(Document.status == doc_status)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": [DocumentOut.model_validate(r).model_dump(mode="json") for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max((total + page_size - 1) // page_size, 1),
    }


def _detail(db: DbSession, document: Document) -> DocumentDetail:
    fragments = list(
        db.scalars(
            select(Fragment)
            .where(Fragment.document_id == document.id)
            .order_by(Fragment.fragment_index)
        )
    )
    verification_count = (
        db.scalar(
            select(func.count())
            .select_from(VerificationLog)
            .where(VerificationLog.document_id == document.id)
        )
        or 0
    )
    last_verified = db.scalar(
        select(func.max(VerificationLog.timestamp)).where(
            VerificationLog.document_id == document.id
        )
    )
    payload = QRPayload(
        version=1,
        document_id=document.id,
        merkle_root=document.merkle_root,
        issued_at=document.created_at.isoformat() if document.created_at else "",
        signature=document.signature,
        key_id=document.key_id or "",
        algorithm=document.algorithm,
    )
    detail = DocumentDetail.model_validate(document)
    detail.owner_name = document.owner.name if document.owner else None
    detail.owner_email = document.owner.email if document.owner else None
    detail.fragments = [FragmentOut.model_validate(f) for f in fragments]
    detail.verification_count = verification_count
    detail.last_verified_at = last_verified
    detail.qr_payload = payload.to_public_dict()
    return detail


def _get_document(db: DbSession, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(db: DbSession, admin: AdminUser, document_id: str) -> DocumentDetail:
    return _detail(db, _get_document(db, document_id))


@router.get("/{document_id}/download")
def download_secured(db: DbSession, admin: AdminUser, document_id: str) -> FileResponse:
    document = _get_document(db, document_id)
    path = Path(document.secured_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Secured file is no longer on disk"
        )
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"secured-{Path(document.document_name).stem}.pdf",
    )


@router.get("/{document_id}/original")
def download_original(db: DbSession, admin: AdminUser, document_id: str) -> FileResponse:
    document = _get_document(db, document_id)
    path = Path(document.original_path)
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Original file is no longer on disk"
        )
    return FileResponse(
        path, media_type="application/pdf", filename=f"original-{document.document_name}"
    )


@router.get("/{document_id}/qr")
def download_qr(db: DbSession, admin: AdminUser, document_id: str) -> FileResponse:
    document = _get_document(db, document_id)
    path = Path(document.qr_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR image not found")
    return FileResponse(path, media_type="image/png", filename=f"qr-{document.id}.png")


@router.get("/{document_id}/pages/{page_index}")
def render_page(
    db: DbSession,
    admin: AdminUser,
    document_id: str,
    page_index: int,
    dpi: int = Query(default=110, ge=50, le=200),
) -> Response:
    document = _get_document(db, document_id)
    path = Path(document.secured_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secured file missing")
    if page_index < 0 or page_index >= document.page_count:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page out of range")
    return Response(
        content=page_png_bytes(path, page_index, dpi),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/{document_id}/revoke", response_model=DocumentOut)
def revoke_document(
    db: DbSession, admin: AdminUser, ip: ClientIP, document_id: str, payload: RevokeRequest
) -> DocumentOut:
    document = _get_document(db, document_id)
    if document.status == DocumentStatus.revoked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Document is already revoked"
        )
    document.status = DocumentStatus.revoked
    document.revoked_reason = payload.reason
    document.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(document)
    audit.record(
        db,
        "document.revoke",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail=f"revoked: {payload.reason}",
        ip_address=ip,
    )
    return DocumentOut.model_validate(document)


@router.post("/{document_id}/reinstate", response_model=DocumentOut)
def reinstate_document(
    db: DbSession, admin: AdminUser, ip: ClientIP, document_id: str
) -> DocumentOut:
    document = _get_document(db, document_id)
    if document.status != DocumentStatus.revoked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Document is not revoked"
        )
    document.status = DocumentStatus.active
    document.revoked_reason = None
    document.revoked_at = None
    db.commit()
    db.refresh(document)
    audit.record(
        db,
        "document.reinstate",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail="revocation lifted",
        ip_address=ip,
    )
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(db: DbSession, admin: AdminUser, ip: ClientIP, document_id: str) -> Response:
    document = _get_document(db, document_id)
    for candidate in (document.secured_path, document.qr_path, document.original_path):
        if candidate:
            Path(candidate).unlink(missing_ok=True)
    audit.record(
        db,
        "document.delete",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail=f"'{document.document_name}' and its {document.fragment_count} fragments removed",
        ip_address=ip,
        commit=False,
    )
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/tamper-sandbox")
def tamper_sandbox(
    db: DbSession, admin: AdminUser, ip: ClientIP, document_id: str, payload: TamperRequest
) -> Response:
    """Return a deliberately altered copy of the secured PDF, for demonstrating
    and testing the detection pipeline. The issued file itself is untouched."""
    document = _get_document(db, document_id)
    source = Path(document.secured_path)
    if not source.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secured file missing")

    out_path = settings.uploads_dir / f"tampered-{uuid.uuid4()}.pdf"
    try:
        info = tamper_pdf(
            source,
            out_path,
            mode=payload.mode,
            page_index=payload.page_index,
            cell_index=payload.cell_index,
            replacement=payload.replacement,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    audit.record(
        db,
        "document.tamper_sandbox",
        user=admin,
        entity_type="document",
        entity_id=document.id,
        detail=info["description"],
        ip_address=ip,
    )
    data = out_path.read_bytes()
    out_path.unlink(missing_ok=True)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="tampered-{document.id[:8]}.pdf"',
            "X-Tamper-Description": info["description"],
        },
    )
