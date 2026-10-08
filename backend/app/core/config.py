"""Application settings, loaded from the environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---
    PROJECT_NAME: str = "QR-Linked Fragmented Watermarking"
    API_V1: str = "/api/v1"
    ENV: str = "development"

    # --- Database ---
    DATABASE_URL: str = "postgresql+psycopg2://localhost:5432/qrwatermark"

    # --- Auth ---
    JWT_SECRET: str = "change-me-in-production-please-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Storage ---
    STORAGE_DIR: Path = BASE_DIR / "storage"
    MAX_UPLOAD_MB: int = 25

    # --- Signing keys ---
    # ES256 keeps the QR payload small enough to scan optically; RSA-PSS-SHA256
    # is also supported (see app/services/signing.py).
    SIGN_ALGORITHM: str = "ES256"
    RSA_KEY_SIZE: int = 2048

    # --- Fragmentation ---
    FRAGMENT_ROWS: int = 6
    FRAGMENT_COLS: int = 2
    FOOTER_BAND_PT: float = 96.0  # reserved, excluded from fragmentation
    RASTER_DPI: int = 100
    ENABLE_RASTER_HASH: bool = True

    # --- Watermarking ---
    DWT_WAVELET: str = "haar"
    DWT_ALPHA: float = 12.0
    DWT_BITS: int = 128
    CARRIER_W: int = 256
    CARRIER_H: int = 64

    # --- Tamper scoring weights ---
    W_FRAGMENT: float = 0.55
    W_MERKLE: float = 0.20
    W_SIGNATURE: float = 0.15
    W_WATERMARK: float = 0.10

    # --- Email (optional) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@docauth.dev"
    SMTP_TLS: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.STORAGE_DIR / "uploads"

    @property
    def secured_dir(self) -> Path:
        return self.STORAGE_DIR / "secured"

    @property
    def qr_dir(self) -> Path:
        return self.STORAGE_DIR / "qr"

    @property
    def reports_dir(self) -> Path:
        return self.STORAGE_DIR / "reports"

    @property
    def renders_dir(self) -> Path:
        return self.STORAGE_DIR / "renders"

    @property
    def keys_dir(self) -> Path:
        return self.STORAGE_DIR / "keys"

    def ensure_dirs(self) -> None:
        for d in (
            self.uploads_dir,
            self.secured_dir,
            self.qr_dir,
            self.reports_dir,
            self.renders_dir,
            self.keys_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()
