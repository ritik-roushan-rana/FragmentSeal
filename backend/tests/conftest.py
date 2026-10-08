"""Test fixtures: an isolated storage dir + SQLite database per test session."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

TMP_ROOT = Path(tempfile.mkdtemp(prefix="docauth-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TMP_ROOT / 'test.db'}"
os.environ["JWT_SECRET"] = "test-secret-not-used-anywhere-real"
os.environ["STORAGE_DIR"] = str(TMP_ROOT / "storage")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

ADMIN = {"email": "admin@docauth.dev", "password": "Admin@12345"}


@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    settings.ensure_dirs()
    Base.metadata.create_all(bind=engine)
    from app.core.security import hash_password
    from app.db.models import User, UserRole

    with SessionLocal() as db:
        db.add(
            User(
                name="Test Admin",
                email=ADMIN["email"],
                role=UserRole.admin,
                password_hash=hash_password(ADMIN["password"]),
                organization="Test University",
            )
        )
        db.commit()
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers(client) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json=ADMIN)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    return TMP_ROOT
