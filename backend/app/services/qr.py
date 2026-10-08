"""QR payload encoding, rendering and decoding.

The QR carries a compact, self-describing JSON envelope:

    {"v":1,"id":<document id>,"r":<merkle root>,"t":<issued at>,
     "s":<base64 RSA-PSS signature>,"k":<key id>,"a":<algorithm>}

Decoding uses OpenCV's QR detector, with pyzbar as a second opinion when the
native zbar library happens to be installed.
"""
from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import qrcode
from PIL import Image
from qrcode.constants import ERROR_CORRECT_Q

try:  # optional: needs the native zbar library (brew install zbar)
    from pyzbar import pyzbar as _pyzbar
except Exception:  # pragma: no cover - depends on host
    _pyzbar = None

PYZBAR_AVAILABLE = _pyzbar is not None


@dataclass
class QRPayload:
    version: int
    document_id: str
    merkle_root: str
    issued_at: str
    signature: str
    key_id: str
    algorithm: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "v": self.version,
                "id": self.document_id,
                "r": self.merkle_root,
                "t": self.issued_at,
                "s": self.signature,
                "k": self.key_id,
                "a": self.algorithm,
            },
            separators=(",", ":"),
        )

    def to_public_dict(self) -> dict:
        return {
            "version": self.version,
            "document_id": self.document_id,
            "merkle_root": self.merkle_root,
            "issued_at": self.issued_at,
            "signature": self.signature,
            "signature_preview": f"{self.signature[:28]}…{self.signature[-12:]}"
            if len(self.signature) > 48
            else self.signature,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
        }

    @staticmethod
    def from_json(raw: str) -> "QRPayload | None":
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict) or "r" not in data or "id" not in data:
            return None
        return QRPayload(
            version=int(data.get("v", 1)),
            document_id=str(data.get("id", "")),
            merkle_root=str(data.get("r", "")),
            issued_at=str(data.get("t", "")),
            signature=str(data.get("s", "")),
            key_id=str(data.get("k", "")),
            algorithm=str(data.get("a", "RSA-PSS-SHA256")),
        )


def render_qr(payload: QRPayload, box_size: int = 6, border: int = 2) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload.to_json())
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def save_qr(payload: QRPayload, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    render_qr(payload).save(path, format="PNG")
    return path


def _decode_with_opencv(image: np.ndarray) -> list[str]:
    detector = cv2.QRCodeDetector()
    results: list[str] = []
    ok, decoded, _, _ = detector.detectAndDecodeMulti(image)
    if ok and decoded:
        results.extend([d for d in decoded if d])
    if not results:
        single, _, _ = detector.detectAndDecode(image)
        if single:
            results.append(single)
    return results


def _decode_with_pyzbar(image: np.ndarray) -> list[str]:
    if _pyzbar is None:
        return []
    try:
        return [
            symbol.data.decode("utf-8", "replace")
            for symbol in _pyzbar.decode(image)
            if symbol.data
        ]
    except Exception:
        return []


def decode_qr_from_image(image: Image.Image) -> list[str]:
    """Decode every QR in a PIL image, trying a few upscales for small stamps."""
    base = np.array(image.convert("RGB"))
    grey = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
    candidates = [grey]

    for factor in (2.0, 3.0):
        candidates.append(
            cv2.resize(grey, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        )
    candidates.append(cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])

    seen: list[str] = []
    for candidate in candidates:
        for text in _decode_with_opencv(candidate) + _decode_with_pyzbar(candidate):
            if text and text not in seen:
                seen.append(text)
        if seen:
            break
    return seen


def decode_qr_from_bytes(data: bytes) -> list[str]:
    return decode_qr_from_image(Image.open(io.BytesIO(data)))


def qr_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()
