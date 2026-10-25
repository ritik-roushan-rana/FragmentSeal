"""Loading and saving documents: images, multi-page PDFs, and QR attachment."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from .pdfwrite import write_image_pdf

#: Rasterisation density for PDF pages. Only 72x2^k is allowed, and that is not
#: a style preference: at any other density the page box is a fractional number
#: of points, pdfium's raster comes back off by a pixel, and the resampling that
#: follows wipes out the watermark. 144 DPI gives a legible A4 page at
#: 1240x1754 while keeping the point box exactly integral.
PDF_DPI_CHOICES = (72, 144, 288, 576)
DEFAULT_DPI = 144

PDF_SUFFIXES = {".pdf"}


def normalise_dpi(dpi: int) -> int:
    """Snap to the nearest density that survives a raster round-trip exactly."""
    return min(PDF_DPI_CHOICES, key=lambda c: (abs(c - dpi), c))


def to_gray(img: np.ndarray) -> np.ndarray:
    """Collapse to one plane, exactly when the image is already neutral.

    A PDF page always comes back as RGB even when it was written as DeviceGray.
    Taking channel 0 in that case keeps the round-trip bit-exact, where a
    luma-weighted sum would drift by a level and flip digest buckets.
    """
    if img.ndim == 2:
        return img
    rgb = img[..., :3]
    if np.array_equal(rgb[..., 0], rgb[..., 1]) and np.array_equal(rgb[..., 1], rgb[..., 2]):
        return rgb[..., 0]
    return np.round(rgb @ [0.299, 0.587, 0.114]).astype(np.uint8)


def is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() in PDF_SUFFIXES


def load_image(path: str | Path) -> np.ndarray:
    img = Image.open(path)
    img = img.convert("L" if img.mode in ("L", "1", "I;16") else "RGB")
    return np.array(img, dtype=np.uint8)


def check_output_path(path: str | Path) -> None:
    """Reject an unusable destination before any work is done.

    Watermarking a page is expensive and writes a manifest sidecar as it goes,
    so a path that was never going to work should fail here rather than after
    the fact, leaving a manifest for a document that does not exist.
    """
    if Path(path).suffix.lower() in (".jpg", ".jpeg"):
        raise ValueError(
            "refusing to write a watermarked document as JPEG: lossy "
            "recompression destroys the fragment tags. Use .png or .pdf."
        )


def save_image(path: str | Path, arr: np.ndarray) -> None:
    check_output_path(path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "L" if arr.ndim == 2 else "RGB").save(path)


def load_pages(path: str | Path, dpi: int = DEFAULT_DPI) -> list[np.ndarray]:
    """Return one array per page, rasterising if the input is a PDF."""
    if not is_pdf(path):
        return [load_image(path)]
    dpi = normalise_dpi(dpi)
    pdf = pdfium.PdfDocument(str(path))
    try:
        return [np.array(page.render(scale=dpi / 72).to_pil().convert("RGB"),
                         dtype=np.uint8)
                for page in pdf]
    finally:
        pdf.close()


def save_pages(path: str | Path, pages: list[np.ndarray], dpi: int = DEFAULT_DPI) -> None:
    """Write pages back out: a multi-page PDF, or a single image file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not is_pdf(path):
        if len(pages) != 1:
            raise ValueError(
                f"{len(pages)} pages cannot go into one image file; "
                f"use a .pdf output path"
            )
        save_image(path, pages[0])
        return
    write_image_pdf(path, pages, dpi=float(normalise_dpi(dpi)))


def attach_qr(doc: np.ndarray, qr: np.ndarray, margin: int = 12) -> np.ndarray:
    """Place the QR anchor on a strip *below* the document, never over it.

    The authenticated region has to stay pixel-identical, so the QR lives
    outside it. A verifier recovers that region by cropping to the dimensions
    the manifest states -- the document always sits at the top-left corner.
    """
    h, w = doc.shape[:2]
    qh, qw = qr.shape[:2]
    strip = qh + 2 * margin
    width = max(w, qw + 2 * margin)
    channels = doc.shape[2] if doc.ndim == 3 else 1

    canvas = np.full((h + strip, width, channels), 255, dtype=np.uint8)
    canvas[:h, :w] = doc.reshape(h, w, channels)
    canvas[h + margin:h + margin + qh, margin:margin + qw] = qr[..., None]
    return canvas[..., 0] if doc.ndim == 2 else canvas


def crop_authenticated(image: np.ndarray, width: int, height: int) -> tuple[np.ndarray, bool]:
    """Recover the authenticated region, dropping any attached QR strip."""
    if image.shape[0] >= height and image.shape[1] >= width:
        return image[:height, :width], image.shape[:2] != (height, width)
    return image, False
