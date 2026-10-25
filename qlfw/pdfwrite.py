"""A minimal, lossless image-per-page PDF writer.

Pillow's PDF export encodes grayscale and RGB pages with DCTDecode -- JPEG --
which silently destroys the fragment tags and turns every page into a false
positive. Nothing in a watermarking pipeline may touch a lossy codec, so the
pages are written here as FlateDecode streams instead: exact bytes in, exact
bytes out.
"""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np


def _stream(dict_entries: str, data: bytes) -> bytes:
    return (f"<< {dict_entries} /Length {len(data)} >>\nstream\n".encode()
            + data + b"\nendstream")


def write_image_pdf(path: str | Path, pages: list[np.ndarray], dpi: float) -> None:
    """Write one full-bleed image per page at the given pixel density."""
    if not pages:
        raise ValueError("cannot write a PDF with no pages")

    objects: list[bytes] = []  # objects[i] is object number i+1

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    add(b"")  # 1: catalog, patched once the page list is known
    add(b"")  # 2: page tree

    page_refs: list[int] = []
    for arr in pages:
        if arr.ndim == 3 and arr.shape[2] == 3:
            colorspace, raw = "/DeviceRGB", arr
        elif arr.ndim == 2:
            colorspace, raw = "/DeviceGray", arr
        else:
            raise ValueError(f"unsupported page shape {arr.shape}; expected HxW or HxWx3")

        h, w = raw.shape[:2]
        img = add(_stream(
            f"/Type /XObject /Subtype /Image /Width {w} /Height {h} "
            f"/ColorSpace {colorspace} /BitsPerComponent 8 /Filter /FlateDecode",
            zlib.compress(np.ascontiguousarray(raw).tobytes(), 6),
        ))
        pw, ph = w * 72.0 / dpi, h * 72.0 / dpi
        content = add(_stream("", f"q {pw:.6f} 0 0 {ph:.6f} 0 0 cm /Im0 Do Q".encode()))
        page_refs.append(add(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.6f} {ph:.6f}] "
            f"/Resources << /XObject << /Im0 {img} 0 R >> /ProcSet [/PDF /ImageB /ImageC] >> "
            f"/Contents {content} 0 R >>".encode()
        ))

    kids = " ".join(f"{n} 0 R" for n in page_refs)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_refs)} >>".encode()

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(out))
