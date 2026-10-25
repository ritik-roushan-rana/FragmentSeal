"""Attack simulation, so the detector can be demonstrated and tested.

These are the edits a forger actually makes to a document: overwrite a figure,
splice a region in from elsewhere on the same page, or recompress to try to
wash the watermark out.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _box(img: np.ndarray, rect: tuple[int, int, int, int]) -> tuple[slice, slice]:
    x, y, w, h = rect
    return slice(max(0, y), min(img.shape[0], y + h)), slice(max(0, x), min(img.shape[1], x + w))


def blank(img: np.ndarray, rect) -> np.ndarray:
    """Erase a region -- the classic "delete the clause" edit."""
    out = img.copy()
    out[_box(out, rect)] = 255
    return out


def write_text(img: np.ndarray, rect, text: str) -> np.ndarray:
    """Overwrite a region with new text -- "change the amount" forgery."""
    x, y, w, h = rect
    pil = Image.fromarray(img, "L" if img.ndim == 2 else "RGB")
    draw = ImageDraw.Draw(pil)
    draw.rectangle([x, y, x + w, y + h], fill=255 if img.ndim == 2 else (255, 255, 255))
    size = max(10, int(h * 0.7))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
    except OSError:
        font = ImageFont.load_default()
    draw.text((x + 2, y + 2), text, fill=0 if img.ndim == 2 else (0, 0, 0), font=font)
    return np.array(pil, dtype=np.uint8)


def splice(img: np.ndarray, src: tuple[int, int], rect) -> np.ndarray:
    """Copy one region of the page over another -- the attack that position-bound
    tags exist to catch: the pasted pixels carry a tag for the wrong index."""
    out = img.copy()
    rs, cs = _box(out, (src[0], src[1], rect[2], rect[3]))
    rd, cd = _box(out, rect)
    h = min(rs.stop - rs.start, rd.stop - rd.start)
    w = min(cs.stop - cs.start, cd.stop - cd.start)
    out[rd.start:rd.start + h, cd.start:cd.start + w] = \
        img[rs.start:rs.start + h, cs.start:cs.start + w]
    return out


def noise(img: np.ndarray, sigma: float = 2.0, seed: int = 0) -> np.ndarray:
    """Global Gaussian noise -- not a forgery, a robustness probe."""
    rng = np.random.default_rng(seed)
    return np.clip(img.astype(np.float64) + rng.normal(0, sigma, img.shape),
                   0, 255).astype(np.uint8)


def jpeg(img: np.ndarray, quality: int = 85) -> np.ndarray:
    """Lossy recompression -- the benign transform a semi-fragile carrier must
    survive and a fragile one must not."""
    import io
    buf = io.BytesIO()
    Image.fromarray(img, "L" if img.ndim == 2 else "RGB").save(
        buf, format="JPEG", quality=quality)
    buf.seek(0)
    return np.array(Image.open(buf), dtype=np.uint8)
