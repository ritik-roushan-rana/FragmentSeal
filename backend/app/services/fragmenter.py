"""PDF fragmentation.

A page's content area (everything above the reserved footer band) is split into
a ROWS x COLS grid. Each grid cell is a *fragment*: the unit at which tampering
is detected and localised.

Each fragment gets two independent digests:

  text_hash   SHA-256 over the normalised text whose words fall inside the cell
              -> catches edited / inserted / deleted text
  raster_hash SHA-256 over the rendered pixels of the cell
              -> catches edited images, vector art, signatures, redactions

fragment_hash = SHA-256("<text_hash>|<raster_hash>") is what goes into the
Merkle tree. Invisible watermark markers stamped into the page are stripped out
before hashing so that stamping is idempotent.
"""
from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

from app.core.config import settings

# Vector-layer watermark marker, e.g. "<WM|7|a3f09c12d4e5>"
MARKER_RE = re.compile(r"<WM\|\d+\|[0-9a-f]{12}>")

# Markers are drawn at MARKER_SIZE (2pt). Anything at or below this threshold is
# treated as marker ink: it is excluded from the text that gets hashed, so that
# stamping a page cannot perturb the hashes of the page it is stamping. Such
# text is still covered by the per-fragment raster hash.
MARKER_MAX_FONT_SIZE = 3.0


@dataclass
class FragmentSpec:
    fragment_index: int
    page_index: int
    cell_index: int
    row: int
    col: int
    x0: float
    y0: float
    x1: float
    y1: float
    page_width: float
    page_height: float
    text_hash: str
    raster_hash: str
    fragment_hash: str
    char_count: int
    text_preview: str
    marker: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_text(raw: str) -> str:
    """Whitespace- and unicode-normalised text, so that cosmetic re-flow of a
    document (different word spacing, NBSPs, ligature forms) does not read as
    tampering while any real character change does."""
    text = unicodedata.normalize("NFKC", raw)
    text = MARKER_RE.sub("", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cell_boxes(
    page_width: float, page_height: float, rows: int, cols: int, footer_pt: float
) -> list[tuple[int, int, int, float, float, float, float]]:
    """Grid over the content area. Returns (cell_index, row, col, x0, y0, x1, y1)
    with y measured from the page top (pdfplumber convention)."""
    content_h = max(page_height - footer_pt, 1.0)
    cell_w = page_width / cols
    cell_h = content_h / rows
    boxes = []
    for row in range(rows):
        for col in range(cols):
            cell_index = row * cols + col
            x0 = col * cell_w
            y0 = row * cell_h
            boxes.append((cell_index, row, col, x0, y0, x0 + cell_w, y0 + cell_h))
    return boxes


def _page_chars(page: "pdfplumber.page.Page") -> list[dict]:
    try:
        return page.chars or []
    except Exception:
        return []


def _chars_to_text(chars: list[dict]) -> str:
    """Rebuild readable text from positioned characters.

    Working at character level (rather than from extract_words) makes the digest
    independent of the word extractor's grouping decisions, which can otherwise
    shift when a tiny marker glyph sits next to real text.
    """
    if not chars:
        return ""
    ordered = sorted(chars, key=lambda c: (round(float(c["top"]), 1), float(c["x0"])))
    parts: list[str] = []
    previous: dict | None = None
    for char in ordered:
        if previous is not None:
            same_line = abs(float(char["top"]) - float(previous["top"])) < 1.5
            gap = float(char["x0"]) - float(previous["x1"])
            width = max(float(previous["x1"]) - float(previous["x0"]), 0.1)
            if not same_line or gap > width * 0.35:
                parts.append(" ")
        parts.append(char.get("text", ""))
        previous = char
    return "".join(parts)


def extract_text_cells(
    pdf_path: Path, rows: int, cols: int, footer_pt: float
) -> tuple[list[dict], list[dict]]:
    """Per-cell normalised text for every page.

    Returns (cells, markers) where `cells` carries geometry + text and `markers`
    carries any watermark markers recovered from the vector text layer.
    """
    cells: list[dict] = []
    markers: list[dict] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            pw, ph = float(page.width), float(page.height)
            boxes = cell_boxes(pw, ph, rows, cols, footer_pt)
            buckets: dict[int, list[dict]] = {b[0]: [] for b in boxes}

            content_limit = max(ph - footer_pt, 1.0)
            cell_w = pw / cols
            cell_h = content_limit / rows

            marker_ink: list[dict] = []
            for char in _page_chars(page):
                try:
                    size = float(char.get("size", 0.0))
                    cx = (float(char["x0"]) + float(char["x1"])) / 2.0
                    cy = (float(char["top"]) + float(char["bottom"])) / 2.0
                except (KeyError, TypeError, ValueError):
                    continue

                if size <= MARKER_MAX_FONT_SIZE:
                    marker_ink.append(char)
                    continue
                if cy >= content_limit:
                    continue  # footer band: reserved, never hashed

                col = min(int(cx / cell_w), cols - 1) if cell_w > 0 else 0
                row = min(int(cy / cell_h), rows - 1) if cell_h > 0 else 0
                buckets[row * cols + col].append(char)

            for found in MARKER_RE.findall(_chars_to_text(marker_ink).replace(" ", "")):
                parsed = found[1:-1].split("|")  # WM|<cell>|<thash12>
                if len(parsed) == 3 and parsed[1].isdigit():
                    markers.append(
                        {
                            "page_index": page_index,
                            "cell_index": int(parsed[1]),
                            "text_hash12": parsed[2],
                        }
                    )

            for cell_index, row, col, x0, y0, x1, y1 in boxes:
                text = normalize_text(_chars_to_text(buckets[cell_index]))
                cells.append(
                    {
                        "page_index": page_index,
                        "cell_index": cell_index,
                        "row": row,
                        "col": col,
                        "x0": x0,
                        "y0": y0,
                        "x1": x1,
                        "y1": y1,
                        "page_width": pw,
                        "page_height": ph,
                        "text": text,
                        "text_hash": sha256_hex(
                            f"{page_index}|{cell_index}|{text}".encode()
                        ),
                    }
                )

    return cells, markers


def render_pages(pdf_path: Path, dpi: int | None = None) -> list[Image.Image]:
    dpi = dpi or settings.RASTER_DPI
    scale = dpi / 72.0
    images: list[Image.Image] = []
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        for index in range(len(doc)):
            page = doc[index]
            bitmap = page.render(scale=scale, draw_annots=False)
            images.append(bitmap.to_pil().convert("L"))
            bitmap.close()
            page.close()
    finally:
        doc.close()
    return images


def raster_hash_for_cell(
    page_image: Image.Image,
    page_width: float,
    page_height: float,
    box: tuple[float, float, float, float],
) -> str:
    """Hash of the rendered pixels of a cell. Quantised to 16 grey levels so
    that sub-pixel antialiasing noise cannot flip the digest, while any visible
    edit does."""
    sx = page_image.width / page_width
    sy = page_image.height / page_height
    x0, y0, x1, y1 = box
    crop = page_image.crop(
        (
            max(int(round(x0 * sx)), 0),
            max(int(round(y0 * sy)), 0),
            min(int(round(x1 * sx)), page_image.width),
            min(int(round(y1 * sy)), page_image.height),
        )
    )
    if crop.width == 0 or crop.height == 0:
        return sha256_hex(b"empty")
    quantised = crop.point(lambda value: (value // 16) * 16)
    return sha256_hex(quantised.tobytes() + f"|{crop.width}x{crop.height}".encode())


def fragment_pdf(
    pdf_path: Path,
    rows: int | None = None,
    cols: int | None = None,
    footer_pt: float | None = None,
    with_raster: bool | None = None,
) -> tuple[list[FragmentSpec], list[dict]]:
    """Fragment a PDF. Returns (fragments in canonical order, watermark markers)."""
    rows = rows or settings.FRAGMENT_ROWS
    cols = cols or settings.FRAGMENT_COLS
    footer_pt = settings.FOOTER_BAND_PT if footer_pt is None else footer_pt
    with_raster = settings.ENABLE_RASTER_HASH if with_raster is None else with_raster

    cells, markers = extract_text_cells(pdf_path, rows, cols, footer_pt)
    page_images = render_pages(pdf_path) if with_raster else []

    fragments: list[FragmentSpec] = []
    for fragment_index, cell in enumerate(
        sorted(cells, key=lambda c: (c["page_index"], c["cell_index"]))
    ):
        raster = ""
        if with_raster and cell["page_index"] < len(page_images):
            raster = raster_hash_for_cell(
                page_images[cell["page_index"]],
                cell["page_width"],
                cell["page_height"],
                (cell["x0"], cell["y0"], cell["x1"], cell["y1"]),
            )
        fragment_hash = sha256_hex(f"{cell['text_hash']}|{raster}".encode())
        fragments.append(
            FragmentSpec(
                fragment_index=fragment_index,
                page_index=cell["page_index"],
                cell_index=cell["cell_index"],
                row=cell["row"],
                col=cell["col"],
                x0=cell["x0"],
                y0=cell["y0"],
                x1=cell["x1"],
                y1=cell["y1"],
                page_width=cell["page_width"],
                page_height=cell["page_height"],
                text_hash=cell["text_hash"],
                raster_hash=raster,
                fragment_hash=fragment_hash,
                char_count=len(cell["text"]),
                text_preview=cell["text"][:160],
            )
        )

    for image in page_images:
        image.close()
    return fragments, markers


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_page_count(pdf_path: Path) -> int:
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        return len(doc)
    finally:
        doc.close()


def page_png_bytes(pdf_path: Path, page_index: int, dpi: int = 110) -> bytes:
    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        page = doc[page_index]
        bitmap = page.render(scale=dpi / 72.0, draw_annots=False)
        image = bitmap.to_pil().convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        bitmap.close()
        page.close()
        return buffer.getvalue()
    finally:
        doc.close()
