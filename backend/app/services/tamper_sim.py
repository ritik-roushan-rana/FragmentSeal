"""Tamper sandbox.

Produces a deliberately altered copy of a secured document so the detection
pipeline can be demonstrated and regression-tested: the alteration is exactly
what a PDF editor does — paint over a region and type something else, or drop
the watermark carrier.
"""
from __future__ import annotations

import io
from pathlib import Path

import pypdf
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.services.fragmenter import cell_boxes

MODES = ("edit_text", "overlay_block", "strip_watermark", "replace_page")


def tamper_pdf(
    source: Path,
    destination: Path,
    mode: str = "edit_text",
    page_index: int = 0,
    cell_index: int = 4,
    replacement: str = "Second Class - Pass",
) -> dict:
    """Return a description of the alteration that was applied."""
    if mode not in MODES:
        raise ValueError(f"unknown tamper mode '{mode}' (expected one of {MODES})")

    reader = pypdf.PdfReader(str(source))
    if page_index >= len(reader.pages):
        raise ValueError(f"page {page_index} does not exist")

    if mode == "replace_page":
        writer = pypdf.PdfWriter()
        for index, page in enumerate(reader.pages):
            if index != page_index:
                writer.add_page(page)
        if len(writer.pages) == 0:
            raise ValueError("cannot delete the only page")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as handle:
            writer.write(handle)
        return {
            "mode": mode,
            "page_index": page_index,
            "cell_index": None,
            "description": f"page {page_index + 1} was removed from the document",
        }

    box = reader.pages[page_index].mediabox
    width, height = float(box.width), float(box.height)
    cells = cell_boxes(
        width, height, settings.FRAGMENT_ROWS, settings.FRAGMENT_COLS, settings.FOOTER_BAND_PT
    )
    target = next((c for c in cells if c[0] == cell_index), cells[0])
    _, row, col, x0, y0, x1, y1 = target

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for index in range(len(reader.pages)):
        page_box = reader.pages[index].mediabox
        pdf.setPageSize((float(page_box.width), float(page_box.height)))
        if index == page_index:
            if mode == "edit_text":
                # Paint the region white, then type a different value over it.
                pdf.setFillColor(colors.white)
                pdf.rect(x0 + 2, height - y1 + 2, (x1 - x0) - 4, (y1 - y0) - 4, stroke=0, fill=1)
                pdf.setFillColor(colors.HexColor("#0f172a"))
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(x0 + 10, height - y0 - 24, replacement)
            elif mode == "overlay_block":
                pdf.setFillColor(colors.HexColor("#111827"))
                pdf.rect(
                    x0 + 6, height - y1 + 6, (x1 - x0) - 12, (y1 - y0) - 12, stroke=0, fill=1
                )
            elif mode == "strip_watermark":
                band = settings.FOOTER_BAND_PT
                pdf.setFillColor(colors.white)
                pdf.rect(0, 0, float(page_box.width), band - 3, stroke=0, fill=1)
        pdf.showPage()
    pdf.save()

    overlay = pypdf.PdfReader(io.BytesIO(buffer.getvalue()))
    writer = pypdf.PdfWriter()
    for index, page in enumerate(reader.pages):
        if index < len(overlay.pages):
            page.merge_page(overlay.pages[index])
        writer.add_page(page)
    if reader.metadata and mode != "strip_watermark":
        writer.add_metadata({k: v for k, v in reader.metadata.items() if isinstance(v, str)})

    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as handle:
        writer.write(handle)

    descriptions = {
        "edit_text": f"text in page {page_index + 1}, grid cell r{row}c{col} was replaced "
        f"with '{replacement}'",
        "overlay_block": f"page {page_index + 1}, grid cell r{row}c{col} was redacted with a "
        f"solid block",
        "strip_watermark": f"the authentication footer on page {page_index + 1} was painted "
        f"over (QR + DWT carrier removed from view)",
    }
    return {
        "mode": mode,
        "page_index": page_index,
        "cell_index": cell_index,
        "row": row,
        "col": col,
        "description": descriptions[mode],
    }
