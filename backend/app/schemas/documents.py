from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DocumentStatus


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_name: str
    owner_id: str
    subject: str | None
    issuer: str | None
    merkle_root: str
    key_id: str | None
    algorithm: str
    status: DocumentStatus
    page_count: int
    fragment_count: int
    grid_rows: int
    grid_cols: int
    revoked_reason: str | None
    revoked_at: datetime | None
    created_at: datetime


class FragmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fragment_index: int
    page_index: int
    cell_index: int
    row: int
    col: int
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float
    fragment_hash: str
    text_hash: str
    raster_hash: str
    char_count: int
    text_preview: str


class DocumentDetail(DocumentOut):
    signature: str
    owner_name: str | None = None
    owner_email: str | None = None
    fragments: list[FragmentOut] = []
    verification_count: int = 0
    last_verified_at: datetime | None = None
    qr_payload: dict | None = None


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TamperRequest(BaseModel):
    mode: str = Field(default="edit_text", pattern="^(edit_text|overlay_block|strip_watermark|replace_page)$")
    page_index: int = Field(default=0, ge=0)
    cell_index: int = Field(default=6, ge=0)
    replacement: str = Field(default="Second Class - Pass", max_length=120)
