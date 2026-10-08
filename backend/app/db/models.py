"""ORM models: users, documents, fragments, verification logs, audit logs, keys."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, new_uuid, utcnow


class UserRole(str, enum.Enum):
    admin = "admin"
    verifier = "verifier"


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    active = "active"
    revoked = "revoked"
    failed = "failed"


class VerificationResult(str, enum.Enum):
    authentic = "authentic"
    tampered = "tampered"
    revoked = "revoked"
    unknown = "unknown"
    invalid = "invalid"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.verifier, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(180), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class SigningKey(Base):
    """RSA keypair used to sign Merkle roots. Rotatable; one active at a time."""

    __tablename__ = "signing_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    key_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), default="ES256", nullable=False)
    public_pem: Mapped[str] = mapped_column(Text, nullable=False)
    private_path: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_name: Mapped[str] = mapped_column(String(300), nullable=False)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(300), nullable=True)

    merkle_root: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    key_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    algorithm: Mapped[str] = mapped_column(String(32), default="ES256", nullable=False)

    original_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    secured_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    qr_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fragment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grid_cols: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    watermark_payload: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.processing,
        nullable=False,
        index=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    owner: Mapped[User] = relationship(back_populates="documents")
    fragments: Mapped[list["Fragment"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    verification_logs: Mapped[list["VerificationLog"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Fragment(Base):
    __tablename__ = "fragments"
    __table_args__ = (
        UniqueConstraint("document_id", "fragment_index", name="uq_fragment_doc_index"),
        Index("ix_fragment_doc_page", "document_id", "page_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    fragment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)
    cell_index: Mapped[int] = mapped_column(Integer, nullable=False)
    row: Mapped[int] = mapped_column(Integer, nullable=False)
    col: Mapped[int] = mapped_column(Integer, nullable=False)

    # Bounding box in PDF points, origin top-left (pdfplumber convention).
    x0: Mapped[float] = mapped_column(Float, nullable=False)
    y0: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    page_width: Mapped[float] = mapped_column(Float, nullable=False)
    page_height: Mapped[float] = mapped_column(Float, nullable=False)

    fragment_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raster_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    text_preview: Mapped[str] = mapped_column(Text, default="", nullable=False)

    document: Mapped[Document] = relationship(back_populates="fragments")


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True
    )
    claimed_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verifier: Mapped[str] = mapped_column(String(255), default="anonymous", nullable=False)
    verifier_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="upload", nullable=False)
    result: Mapped[VerificationResult] = mapped_column(
        Enum(VerificationResult, name="verification_result"),
        default=VerificationResult.unknown,
        nullable=False,
        index=True,
    )
    tamper_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fragments_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fragments_modified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    merkle_match: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    watermark_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    qr_found: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_name: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    report_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    document: Mapped[Document | None] = relationship(back_populates="verification_logs")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
