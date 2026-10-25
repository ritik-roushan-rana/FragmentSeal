"""The QR-side manifest: the public anchor a verifier reads before touching pixels.

The manifest never contains the secret key and never contains the fragment tags
-- only the Merkle root over them. That is the point of the QR link: it binds a
sheet of paper to one exact set of fragment authenticators, compactly, while
the authenticators themselves stay hidden in the pixels.

Two decisions here are driven by measurement rather than taste.

The record is a packed binary struct in base32, not JSON. OpenCV's QR decoder
is reliable up to around symbol version 8 and starts dropping roughly one read
in thirty beyond it, so bytes removed from this format are reliability gained
on real paper. Base32's alphabet also falls inside QR alphanumeric mode, which
spends 5.5 bits per character where byte mode spends 8.

The issuer's public key is deliberately *not* in the record. A key carried by
the document it signs attests to nothing -- a forger re-signs with their own
key and presents that. The verifier has to supply the key it expects, so the
question becomes "is this from the issuer I trust", which is the one worth
asking.
"""

from __future__ import annotations

import base64
import dataclasses
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone

import cv2
import numpy as np
import qrcode

from . import crypto
from .config import CARRIER_CODES, Params

FORMAT_VERSION = 3
_PREFIX = "QLFW:"
_MAGIC = 0xB1

#: magic+version, flags, doc_id, width, height, fragment, tag_bytes, carrier,
#: strength in quarter-steps, unix seconds, merkle root. The fragment grid is
#: not stored: it follows from the dimensions and the fragment size.
_HEAD = struct.Struct(">BB8sHHBBBBI32s")
_FLAG_SIGNED = 0x01
_SIG_LEN = 64

#: Symbol version at which commodity decoders stay dependable. Exceeding it is
#: not an error, but it is worth telling the operator about.
SAFE_QR_VERSION = 8

_ECC_LEVELS = {"L": qrcode.constants.ERROR_CORRECT_L,
               "M": qrcode.constants.ERROR_CORRECT_M,
               "Q": qrcode.constants.ERROR_CORRECT_Q,
               "H": qrcode.constants.ERROR_CORRECT_H}

#: Tried in this order when rendering. Q first for damage tolerance; the
#: lighter levels are fallbacks that shrink the symbol if Q will not read back.
ECC_PREFERENCE = ("Q", "M", "H", "L")


def _b32(raw: bytes) -> str:
    return base64.b32encode(raw).decode().rstrip("=")


def _unb32(text: str) -> bytes:
    return base64.b32decode(text + "=" * (-len(text) % 8))


@dataclass
class Manifest:
    doc_id: str
    width: int
    height: int
    params: Params
    merkle_root: bytes
    signature: bytes = b""
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc)
                           .replace(microsecond=0).isoformat())
    note: str = ""

    # --- canonical form ----------------------------------------------------

    def signing_bytes(self) -> bytes:
        """Everything the signature covers: the record but for the signature.

        A forger cannot swap the root, the scheme parameters, the issue date or
        the note without invalidating it.
        """
        p = self.params
        note = self.note.encode()
        head = _HEAD.pack(
            _MAGIC, (FORMAT_VERSION << 1) | (_FLAG_SIGNED if self.signature else 0),
            bytes.fromhex(self.doc_id), self.width, self.height,
            p.fragment, p.tag_bits // 8, CARRIER_CODES[p.carrier],
            round(p.strength * 4),
            int(datetime.fromisoformat(self.issued_at).timestamp()),
            self.merkle_root,
        )
        return head + len(note).to_bytes(1, "big") + note

    def sign_with(self, private_raw: bytes) -> None:
        # The signed flag is part of the signed bytes, so set it before signing.
        self.signature = b"\x00" * _SIG_LEN
        self.signature = crypto.sign(private_raw, self.signing_bytes())

    def signature_ok(self, issuer_key: bytes | None) -> bool | None:
        """Whether this manifest was signed by ``issuer_key``.

        ``None`` means the question could not be asked: either the document was
        issued unsigned, or the verifier named no issuer to check against.
        """
        if not self.signature or not issuer_key:
            return None
        signed = self.signature
        try:
            self.signature = b"\x00" * _SIG_LEN
            message = self.signing_bytes()
        finally:
            self.signature = signed
        return crypto.verify_signature(issuer_key, message, signed)

    # --- wire form ---------------------------------------------------------

    def encode(self) -> str:
        return _PREFIX + _b32(self.signing_bytes() + self.signature)

    @classmethod
    def decode(cls, text: str) -> "Manifest":
        text = text.strip()
        if not text.startswith(_PREFIX):
            raise ValueError("not a QLFW manifest")
        raw = _unb32(text[len(_PREFIX):])
        if len(raw) < _HEAD.size + 1:
            raise ValueError("truncated QLFW manifest")

        (magic, verflags, doc_id, w, h, fragment, tag_bytes, carrier,
         quarters, ts, root) = _HEAD.unpack(raw[:_HEAD.size])
        if magic != _MAGIC:
            raise ValueError("not a QLFW manifest")
        if verflags >> 1 != FORMAT_VERSION:
            raise ValueError(f"unsupported manifest version {verflags >> 1}")

        note_len = raw[_HEAD.size]
        at = _HEAD.size + 1
        note = raw[at:at + note_len].decode("utf-8", "replace")
        at += note_len
        signature = raw[at:at + _SIG_LEN] if verflags & _FLAG_SIGNED else b""
        if verflags & _FLAG_SIGNED and len(signature) != _SIG_LEN:
            raise ValueError("manifest claims a signature but does not carry one")

        names = {v: k for k, v in CARRIER_CODES.items()}
        if carrier not in names:
            raise ValueError(f"unknown carrier code {carrier}")
        if fragment == 0 or w % fragment or h % fragment:
            raise ValueError("manifest dimensions do not tile into fragments")

        return cls(
            doc_id=doc_id.hex(), width=w, height=h,
            params=Params(fragment=fragment, tag_bits=tag_bytes * 8,
                          carrier=names[carrier], strength=quarters / 4)
                   .with_grid(h // fragment, w // fragment),
            merkle_root=root, signature=signature,
            issued_at=datetime.fromtimestamp(ts, timezone.utc).isoformat(),
            note=note,
        )

    def summary(self) -> dict:
        out = dataclasses.asdict(self.params)
        out.update(doc_id=self.doc_id, size=f"{self.width}x{self.height}",
                   fragments=self.params.n_fragments,
                   root=self.merkle_root.hex(),
                   signed=bool(self.signature),
                   issued_at=self.issued_at, note=self.note)
        return out


# --- QR rendering and reading ----------------------------------------------

def _render(text: str, ecc: str, box: int, border: int):
    qr = qrcode.QRCode(error_correction=_ECC_LEVELS[ecc], box_size=box,
                       border=border)
    qr.add_data(text)
    qr.make(fit=True)
    img = np.array(qr.make_image(fill_color="black", back_color="white")
                   .convert("L"), dtype=np.uint8)
    return img, qr.version


def to_qr_image(manifest: Manifest, box: int = 4, border: int = 4,
                ecc: str = "Q") -> tuple[np.ndarray, int]:
    """Render the anchor as a QR code. Returns the image and symbol version."""
    if ecc not in _ECC_LEVELS:
        raise ValueError(f"unknown error-correction level {ecc!r}")
    return _render(manifest.encode(), ecc, box, border)


def readable_qr(manifest: Manifest, compose, box: int = 4,
                border: int = 4) -> tuple[np.ndarray, str, int]:
    """Render and place the QR, then prove the *finished page* decodes.

    A document whose anchor cannot be read is worthless however sound the
    watermark is, and commodity decoders fail on a minority of dense symbols
    for reasons no amount of image quality fixes. Checking the bare symbol is
    not enough either -- placing it on a page changes whether it reads. So the
    composed page is decoded here, and the error-correction level stepped
    through until one survives the whole trip.

    ``compose(qr_image) -> page`` places the symbol exactly as it will ship.
    Returns the composed page, the level used and the symbol version.
    """
    text = manifest.encode()
    for level in ECC_PREFERENCE:
        qr, version = _render(text, level, box, border)
        page = compose(qr)
        if _decode_text(page if page.ndim == 2
                        else cv2.cvtColor(page, cv2.COLOR_RGB2GRAY)) == text:
            return page, level, version
    raise ValueError(
        "could not place a QR code that decodes back off the finished page; "
        "shorten --note, or raise --qr-box to enlarge the symbol"
    )


def _decode_text(gray: np.ndarray) -> str | None:
    detector = cv2.QRCodeDetector()
    views = [gray,
             cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST),
             cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA),
             cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]]
    for view in views:
        ok, texts, _, _ = detector.detectAndDecodeMulti(view)
        single, _, _ = detector.detectAndDecode(view)
        for text in (list(texts) if ok else []) + ([single] if single else []):
            if text.startswith(_PREFIX):
                return text
    return None


def read_qr(image: np.ndarray) -> Manifest:
    """Locate and decode a QLFW QR anywhere in the image."""
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    text = _decode_text(gray)
    if text is None:
        raise ValueError("no QLFW QR code found in the image")
    return Manifest.decode(text)
