"""Digital signatures over Merkle roots, with a DB-backed key registry.

Two algorithms are supported:

  ES256            ECDSA on P-256, signature serialised as raw r||s (64 bytes)
                   -> ~88 base64 characters, which keeps the QR code sparse
                   enough to scan with a phone camera. This is the default.
  RSA-PSS-SHA256   RSA-PSS with SHA-256 and digest-length salt. A 2048-bit
                   signature is 344 base64 characters, which pushes the QR to
                   ~105 modules; usable for file-based verification, but set
                   a larger footer band if you need it to scan optically.

Keys live in `signing_keys`; the private key is written to STORAGE_DIR/keys with
0600 permissions. Exactly one key is active at a time, and verification tries
every registered key so rotation does not invalidate older documents.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import SigningKey

ES256 = "ES256"
RSA_PSS = "RSA-PSS-SHA256"
SUPPORTED = (ES256, RSA_PSS)


def b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def b64u_decode(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def _pss() -> padding.AsymmetricPadding:
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH)


# --------------------------------------------------------------------------- #
# key management
# --------------------------------------------------------------------------- #
def generate_keypair(algorithm: str) -> tuple[bytes, bytes]:
    """Returns (private PEM, public PEM)."""
    if algorithm == ES256:
        private_key: ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey = ec.generate_private_key(
            ec.SECP256R1()
        )
    elif algorithm == RSA_PSS:
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=settings.RSA_KEY_SIZE
        )
    else:
        raise ValueError(f"unsupported signing algorithm '{algorithm}'")

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def get_or_create_active_key(db: Session, algorithm: str | None = None) -> SigningKey:
    algorithm = algorithm or settings.SIGN_ALGORITHM
    key = db.scalar(
        select(SigningKey).where(
            SigningKey.is_active.is_(True), SigningKey.algorithm == algorithm
        )
    )
    if key:
        return key

    private_pem, public_pem = generate_keypair(algorithm)
    key_id = hashlib.sha256(public_pem).hexdigest()[:16]
    path = settings.keys_dir / f"{key_id}.pem"
    path.write_bytes(private_pem)
    path.chmod(0o600)

    db.execute(
        SigningKey.__table__.update()
        .where(SigningKey.algorithm == algorithm)
        .values(is_active=False)
    )
    key = SigningKey(
        key_id=key_id,
        algorithm=algorithm,
        public_pem=public_pem.decode(),
        private_path=str(path),
        is_active=True,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return key


def rotate_key(db: Session, algorithm: str | None = None) -> SigningKey:
    """Issue a fresh keypair. Documents signed with the previous key still
    verify, because verification walks every registered key."""
    algorithm = algorithm or settings.SIGN_ALGORITHM
    db.execute(
        SigningKey.__table__.update()
        .where(SigningKey.algorithm == algorithm)
        .values(is_active=False)
    )
    db.commit()
    return get_or_create_active_key(db, algorithm)


def _load_private(key: SigningKey):
    loaded = serialization.load_pem_private_key(Path(key.private_path).read_bytes(), password=None)
    return loaded


# --------------------------------------------------------------------------- #
# sign / verify
# --------------------------------------------------------------------------- #
def sign_root(db: Session, merkle_root: str) -> tuple[str, str, str]:
    """Sign a Merkle root. Returns (signature, key_id, algorithm)."""
    key = get_or_create_active_key(db)
    private_key = _load_private(key)
    message = merkle_root.encode()

    if key.algorithm == ES256:
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            raise TypeError("registered ES256 key is not an EC private key")
        der = private_key.sign(message, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        signature = b64u_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    else:
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise TypeError("registered RSA key is not an RSA private key")
        signature = b64u_encode(private_key.sign(message, _pss(), hashes.SHA256()))

    return signature, key.key_id, key.algorithm


def _verify_with_key(key: SigningKey, merkle_root: str, signature: str) -> bool:
    try:
        raw = b64u_decode(signature)
    except Exception:
        try:  # tolerate standard base64 from older payloads
            raw = base64.b64decode(signature + "=" * (-len(signature) % 4))
        except Exception:
            return False

    try:
        public_key = serialization.load_pem_public_key(key.public_pem.encode())
    except Exception:
        return False

    message = merkle_root.encode()
    try:
        if key.algorithm == ES256:
            if not isinstance(public_key, ec.EllipticCurvePublicKey) or len(raw) != 64:
                return False
            der = encode_dss_signature(
                int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big")
            )
            public_key.verify(der, message, ec.ECDSA(hashes.SHA256()))
            return True
        if not isinstance(public_key, rsa.RSAPublicKey):
            return False
        public_key.verify(raw, message, _pss(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError):
        return False


def verify_root_signature(
    db: Session, merkle_root: str, signature: str, key_id: str | None = None
) -> bool:
    if not merkle_root or not signature:
        return False

    if key_id:
        key = db.scalar(select(SigningKey).where(SigningKey.key_id == key_id))
        if key is not None:
            return _verify_with_key(key, merkle_root, signature)
        # Unknown key id: fall through and try the register, so a forged key id
        # on an otherwise genuine signature is still caught as valid-or-not.
    return any(
        _verify_with_key(key, merkle_root, signature) for key in db.scalars(select(SigningKey))
    )


def active_public_pem(db: Session) -> str:
    return get_or_create_active_key(db).public_pem
