"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import audit as audit_routes
from app.api.routes import auth, dashboard, documents, verify
from app.core.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.services.qr import PYZBAR_AVAILABLE
from app.services.signing import get_or_create_active_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
logger = logging.getLogger("docauth")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        key = get_or_create_active_key(db)
        logger.info("active signing key %s (%s)", key.key_id, key.algorithm)
    logger.info("QR decoders: opencv=yes pyzbar=%s", "yes" if PYZBAR_AVAILABLE else "no")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Tamper-evident document authentication: documents are split into "
        "fragments, each fragment is hashed with SHA-256, the hashes form a "
        "Merkle tree whose root is signed with RSA-PSS and published through a "
        "QR code, and semi-fragile DWT watermarks are embedded per fragment so "
        "that tampering can be localised to a region of a page."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Tamper-Description"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal error: {type(exc).__name__}"},
    )


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENV,
        "fragment_grid": f"{settings.FRAGMENT_ROWS}x{settings.FRAGMENT_COLS}",
        "raster_hashing": settings.ENABLE_RASTER_HASH,
        "qr_decoders": {"opencv": True, "pyzbar": PYZBAR_AVAILABLE},
    }


for router in (
    auth.router,
    documents.router,
    verify.router,
    dashboard.router,
    audit_routes.router,
):
    app.include_router(router, prefix=settings.API_V1)
