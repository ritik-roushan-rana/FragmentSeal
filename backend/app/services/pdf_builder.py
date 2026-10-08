"""Secured-PDF construction and introspection.

Two stamping passes are applied to the source PDF:

1. `stamp_fragment_markers` draws one near-invisible marker per grid cell,
   carrying the first 12 hex digits of that fragment's text hash. This is the
   *fragmented* watermark: every region of the page carries evidence about
   itself, so a region can be shown to have been altered even if the QR stamp
   or the footer is cut away.

2. `stamp_footer` fills the reserved footer band with the QR code, the DWT
   watermark carrier and human-readable issuance text, and writes the full
   verification manifest into the PDF metadata.

The footer band is excluded from fragmentation, which is what lets the QR
(whose payload contains the Merkle root) be added *after* hashing without
invalidating the hashes.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

import pypdf
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.services.fragmenter import cell_boxes
from app.services.watermark import WM_IMAGE_KEY

MANIFEST_KEY = "/DocAuthManifest"
MARKER_FONT = "Helvetica"
MARKER_SIZE = 2.0
MARKER_INK = colors.Color(0.96, 0.96, 0.96)


def marker_text(cell_index: int, text_hash: str) -> str:
    return f"<WM|{cell_index}|{text_hash[:12]}>"


def _page_sizes(reader: pypdf.PdfReader) -> list[tuple[float, float]]:
    sizes = []
    for page in reader.pages:
        box = page.mediabox
        sizes.append((float(box.width), float(box.height)))
    return sizes


def _merge_overlay(src: Path, dst: Path, overlay_pdf: bytes) -> Path:
    reader = pypdf.PdfReader(str(src))
    overlay = pypdf.PdfReader(io.BytesIO(overlay_pdf))
    writer = pypdf.PdfWriter()
    for index, page in enumerate(reader.pages):
        if index < len(overlay.pages):
            page.merge_page(overlay.pages[index])
        writer.add_page(page)
    if reader.metadata:
        writer.add_metadata({k: v for k, v in reader.metadata.items() if isinstance(v, str)})
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "wb") as handle:
        writer.write(handle)
    return dst


def stamp_fragment_markers(
    src: Path, dst: Path, text_hashes: dict[tuple[int, int], str]
) -> Path:
    """Draw the per-fragment invisible markers. `text_hashes` maps
    (page_index, cell_index) -> text hash."""
    reader = pypdf.PdfReader(str(src))
    sizes = _page_sizes(reader)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for page_index, (width, height) in enumerate(sizes):
        pdf.setPageSize((width, height))
        pdf.setFont(MARKER_FONT, MARKER_SIZE)
        pdf.setFillColor(MARKER_INK)
        for cell_index, _row, _col, x0, _y0, _x1, y1 in cell_boxes(
            width, height, settings.FRAGMENT_ROWS, settings.FRAGMENT_COLS,
            settings.FOOTER_BAND_PT,
        ):
            text_hash = text_hashes.get((page_index, cell_index))
            if not text_hash:
                continue
            # reportlab's origin is bottom-left; cell boxes are top-left based.
            pdf.drawString(x0 + 2.0, height - y1 + 1.5, marker_text(cell_index, text_hash))
        pdf.showPage()
    pdf.save()
    return _merge_overlay(src, dst, buffer.getvalue())


def stamp_footer(
    src: Path,
    dst: Path,
    qr_image: Image.Image,
    carrier_image: Image.Image,
    labels: dict[str, str],
    manifest: dict,
) -> Path:
    """Fill the reserved footer band and attach the verification manifest."""
    reader = pypdf.PdfReader(str(src))
    sizes = _page_sizes(reader)
    total_pages = len(sizes)

    qr_reader = ImageReader(qr_image)
    carrier_reader = ImageReader(carrier_image)

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for page_index, (width, height) in enumerate(sizes):
        band = settings.FOOTER_BAND_PT
        pdf.setPageSize((width, height))

        pdf.setFillColor(colors.Color(0.98, 0.985, 0.995))
        pdf.rect(0, 0, width, band, stroke=0, fill=1)
        pdf.setStrokeColor(colors.Color(0.80, 0.84, 0.90))
        pdf.setLineWidth(0.6)
        pdf.line(18, band - 2, width - 18, band - 2)

        qr_side = band - 22
        qr_x = width - 18 - qr_side
        pdf.drawImage(qr_reader, qr_x, 11, qr_side, qr_side, mask=None)

        # DWT watermark carrier: low-contrast strip, lossless in the PDF.
        carrier_w = min(160.0, max(70.0, width * 0.24))
        carrier_h = carrier_w * (carrier_image.height / carrier_image.width)
        pdf.drawImage(
            carrier_reader, qr_x - carrier_w - 14, 12, carrier_w, carrier_h, mask=None
        )

        text_x = 20
        pdf.setFillColor(colors.Color(0.10, 0.14, 0.22))
        pdf.setFont("Helvetica-Bold", 8.2)
        pdf.drawString(text_x, band - 17, labels.get("title", "AUTHENTICATED DOCUMENT"))
        pdf.setFont("Helvetica", 6.6)
        pdf.setFillColor(colors.Color(0.26, 0.31, 0.40))
        lines = [
            f"Document ID: {labels.get('document_id', '')}",
            f"Merkle Root: {labels.get('merkle_root', '')[:48]}…",
            f"Issued: {labels.get('issued_at', '')}  |  Key: {labels.get('key_id', '')}"
            f"  |  Alg: {labels.get('algorithm', '')}",
            f"Fragments: {labels.get('fragment_count', '')}"
            f"  |  Grid: {labels.get('grid', '')}"
            f"  |  Page {page_index + 1}/{total_pages}",
            "Scan the QR code or upload this file to verify integrity.",
        ]
        for offset, line in enumerate(lines):
            pdf.drawString(text_x, band - 30 - offset * 9.4, line)
        pdf.showPage()
    pdf.save()

    _merge_overlay(src, dst, buffer.getvalue())

    writer = pypdf.PdfWriter(clone_from=str(dst))
    writer.add_metadata(
        {
            "/Title": labels.get("document_name", "Authenticated Document"),
            "/Producer": "QR-Linked Fragmented Watermarking Platform",
            "/Subject": f"Authenticated document {labels.get('document_id', '')}",
            MANIFEST_KEY: base64.b64encode(
                json.dumps(manifest, separators=(",", ":")).encode()
            ).decode(),
        }
    )
    with open(dst, "wb") as handle:
        writer.write(handle)
    return dst


# --------------------------------------------------------------------------- #
# introspection used during verification
# --------------------------------------------------------------------------- #
def read_manifest(pdf_path: Path) -> dict | None:
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        metadata = reader.metadata or {}
        raw = metadata.get(MANIFEST_KEY)
        if not raw:
            return None
        return json.loads(base64.b64decode(str(raw)).decode())
    except Exception:
        return None


def extract_carrier_image(pdf_path: Path) -> Image.Image | None:
    """Pull the DWT carrier back out of the PDF's image XObjects, matching it by
    its exact pixel dimensions."""
    target = (settings.CARRIER_W, settings.CARRIER_H)
    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception:
        return None

    for page in reader.pages:
        try:
            images = list(page.images)
        except Exception:
            continue
        for embedded in images:
            try:
                image = Image.open(io.BytesIO(embedded.data))
            except Exception:
                continue
            if image.size == target:
                return image.convert("L")
    return None


DECODE_DPIS = (300, 400, 240, 500)


def extract_footer_qr_payloads(
    pdf_path: Path, dpis: tuple[int, ...] = DECODE_DPIS
) -> list[str]:
    """Render each page's footer band and decode any QR found there.

    Dense payloads need enough pixels per module, while very high resolutions
    can actually hurt the detector, so a few render scales are tried in turn.
    """
    import pypdfium2 as pdfium

    from app.services.qr import decode_qr_from_image

    payloads: list[str] = []
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for dpi in dpis:
            scale = dpi / 72.0
            for index in range(len(doc)):
                page = doc[index]
                bitmap = page.render(scale=scale, draw_annots=False)
                image = bitmap.to_pil().convert("RGB")
                bitmap.close()
                page.close()
                band_px = int(settings.FOOTER_BAND_PT * scale) + 10
                footer = image.crop(
                    (0, max(image.height - band_px, 0), image.width, image.height)
                )
                for text in decode_qr_from_image(footer) or decode_qr_from_image(image):
                    if text not in payloads:
                        payloads.append(text)
                image.close()
                if payloads:
                    return payloads
    finally:
        doc.close()
    return payloads


def watermark_key(document_id: str) -> str:
    return f"{WM_IMAGE_KEY}:{document_id}"
