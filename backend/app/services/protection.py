"""The document protection pipeline (admin side).

    original PDF
      -> text fragments (grid cells)            [fragmenter]
      -> invisible per-fragment markers stamped [pdf_builder]
      -> fragment hashes (text + raster)        [fragmenter]
      -> Merkle tree + root                     [merkle]
      -> RSA-PSS signature over the root        [signing]
      -> QR payload + PNG                       [qr]
      -> DWT watermark carrier from the root     [watermark]
      -> footer stamp + embedded manifest        [pdf_builder]
      -> secured PDF
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.core.config import settings
from app.services import pdf_builder
from app.services.fragmenter import FragmentSpec, fragment_pdf, pdf_page_count
from app.services.merkle import MerkleTree
from app.services.qr import QRPayload, render_qr
from app.services.watermark import build_watermark_image

SignFn = Callable[[str], tuple[str, str, str]]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def protect_pdf(
    source: Path,
    document_id: str,
    document_name: str,
    sign: SignFn,
    secured_path: Path,
    qr_path: Path,
    issuer: str | None = None,
    subject: str | None = None,
    work_dir: Path | None = None,
) -> dict:
    """Produce the secured PDF and return everything worth persisting."""
    work_dir = work_dir or secured_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    marked_path = work_dir / f"{document_id}.marked.pdf"

    # 1-2. text-level fragmentation of the untouched source
    text_fragments, _ = fragment_pdf(source, with_raster=False)
    text_hashes = {(f.page_index, f.cell_index): f.text_hash for f in text_fragments}

    # 3. stamp the fragmented invisible watermark markers
    pdf_builder.stamp_fragment_markers(source, marked_path, text_hashes)

    # 4. final fragment hashes over the marked document (text + rendered pixels)
    fragments, markers = fragment_pdf(marked_path)

    # 5-6. Merkle tree and root
    tree = MerkleTree([f.fragment_hash for f in fragments])
    merkle_root = tree.root

    # 7. sign the root
    signature, key_id, algorithm = sign(merkle_root)
    issued_at = _iso_now()

    # 8. QR payload
    payload = QRPayload(
        version=1,
        document_id=document_id,
        merkle_root=merkle_root,
        issued_at=issued_at,
        signature=signature,
        key_id=key_id,
        algorithm=algorithm,
    )
    qr_path.parent.mkdir(parents=True, exist_ok=True)
    qr_image = render_qr(payload)
    qr_image.save(qr_path, format="PNG")

    # 9. DWT watermark carrier derived from the root
    wm_key = pdf_builder.watermark_key(document_id)
    carrier = build_watermark_image(merkle_root, wm_key)

    # 10. footer stamp + embedded manifest
    manifest = {
        "version": 1,
        "document_id": document_id,
        "document_name": document_name,
        "merkle_root": merkle_root,
        "signature": signature,
        "key_id": key_id,
        "algorithm": algorithm,
        "issued_at": issued_at,
        "issuer": issuer,
        "subject": subject,
        "grid": {"rows": settings.FRAGMENT_ROWS, "cols": settings.FRAGMENT_COLS},
        "footer_band_pt": settings.FOOTER_BAND_PT,
        "raster_dpi": settings.RASTER_DPI,
        "raster_hash_enabled": settings.ENABLE_RASTER_HASH,
        "dwt": {
            "wavelet": settings.DWT_WAVELET,
            "bits": settings.DWT_BITS,
            "delta": settings.DWT_ALPHA,
        },
        "fragments": [
            {
                "i": f.fragment_index,
                "p": f.page_index,
                "c": f.cell_index,
                "h": f.fragment_hash,
                "t": f.text_hash,
            }
            for f in fragments
        ],
    }
    labels = {
        "title": "AUTHENTICATED DOCUMENT · TAMPER-EVIDENT",
        "document_id": document_id,
        "document_name": document_name,
        "merkle_root": merkle_root,
        "issued_at": issued_at,
        "key_id": key_id,
        "algorithm": algorithm,
        "fragment_count": str(len(fragments)),
        "grid": f"{settings.FRAGMENT_ROWS}x{settings.FRAGMENT_COLS}",
    }
    pdf_builder.stamp_footer(marked_path, secured_path, qr_image, carrier, labels, manifest)

    marked_path.unlink(missing_ok=True)

    return {
        "merkle_root": merkle_root,
        "signature": signature,
        "key_id": key_id,
        "algorithm": algorithm,
        "issued_at": issued_at,
        "fragments": fragments,
        "markers": markers,
        "manifest": manifest,
        "qr_payload": payload,
        "page_count": pdf_page_count(secured_path),
        "watermark_key": wm_key,
    }


def fragment_rows(fragments: list[FragmentSpec]) -> list[dict]:
    return [f.to_dict() for f in fragments]
