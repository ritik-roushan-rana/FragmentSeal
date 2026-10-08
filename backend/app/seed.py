"""Create the schema and seed demo accounts (and optionally demo documents).

    python -m app.seed              # schema + users
    python -m app.seed --documents  # also issue two protected sample documents
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import User, UserRole
from app.db.session import SessionLocal, engine
from app.services import audit, signing

DEMO_USERS = [
    {
        "name": "Platform Administrator",
        "email": "admin@docauth.dev",
        "password": "Admin@12345",
        "role": UserRole.admin,
        "organization": "National Institute of Technology",
    },
    {
        "name": "Verification Officer",
        "email": "verifier@docauth.dev",
        "password": "Verify@12345",
        "role": UserRole.verifier,
        "organization": "Global Employment Services",
    },
]


def seed(with_documents: bool = False) -> None:
    settings.ensure_dirs()
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        key = signing.get_or_create_active_key(db)
        print(f"signing key: {key.key_id} ({key.algorithm})")

        created = []
        for spec in DEMO_USERS:
            existing = db.scalar(select(User).where(User.email == spec["email"]))
            if existing:
                print(f"user exists: {spec['email']}")
                continue
            user = User(
                name=spec["name"],
                email=spec["email"],
                role=spec["role"],
                password_hash=hash_password(spec["password"]),
                organization=spec["organization"],
            )
            db.add(user)
            created.append(spec)
        db.commit()
        for spec in created:
            print(f"created {spec['role'].value}: {spec['email']} / {spec['password']}")

        if not with_documents:
            return

        from app.api.routes.documents import _protect_one
        from app.services.sample_docs import build_certificate, build_transcript

        admin = db.scalar(select(User).where(User.role == UserRole.admin))
        if admin is None:
            print("no admin to own the sample documents")
            return
        for builder, name in (
            (build_certificate, "degree-certificate.pdf"),
            (build_transcript, "academic-transcript.pdf"),
        ):
            staged = settings.uploads_dir / f"{uuid.uuid4()}.pdf"
            builder(staged)
            document = _protect_one(db, admin, staged, name, "Aarav Sharma", None, None)
            print(f"issued {name}: {document.id} root={document.merkle_root[:16]}…")
        audit.record(db, "system.seed", user=admin, detail="demo documents issued")


if __name__ == "__main__":
    seed(with_documents="--documents" in sys.argv)
