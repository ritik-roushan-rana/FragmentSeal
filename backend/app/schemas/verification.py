from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.db.models import VerificationResult


class VerificationResponse(BaseModel):
    log_id: str
    result: str
    tamper_score: float
    verified_at: str
    duration_ms: int
    file: dict
    document: dict
    qr: dict
    manifest_present: bool
    baseline_source: str
    signature: dict
    merkle: dict
    watermark: dict
    fragments: dict
    heatmap: list[dict]
    revoked: bool
    revoked_reason: str | None
    timeline: list[dict]


class VerificationLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str | None
    claimed_document_id: str | None
    verifier: str
    source: str
    result: VerificationResult
    tamper_score: float
    fragments_total: int
    fragments_modified: int
    signature_valid: bool
    merkle_match: bool
    watermark_valid: bool
    qr_found: bool
    file_name: str
    file_sha256: str
    timestamp: datetime


class EmailReportRequest(BaseModel):
    to: EmailStr
    note: str | None = None
