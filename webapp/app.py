"""Local web interface for QLFW, for demonstrating the scheme interactively.

This is a thin shell over the same library the command line uses -- it adds no
cryptography of its own. It binds to localhost only and is meant for a live
demonstration on one machine, not for deployment.
"""

from __future__ import annotations

import secrets
import sys
import traceback
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request, send_from_directory
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qlfw import docio, report, tamper as attacks           # noqa: E402
from qlfw.cli import _authenticated_extent, _random_rect      # noqa: E402
from qlfw.config import Params                               # noqa: E402
from qlfw.keystore import KeyFile                            # noqa: E402
from qlfw.manifest import Manifest, read_qr, readable_qr     # noqa: E402
from qlfw.pipeline import embed, verify                      # noqa: E402

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "workspace"
KEYFILE = WORK / "issuer.key"
ALLOWED = {".png", ".jpg", ".jpeg", ".pdf", ".bmp", ".tif", ".tiff"}
MAX_PIXELS = 40_000_000     # refuse absurd uploads rather than exhausting memory

app = Flask(__name__, static_folder=str(ROOT / "static"), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024


def issuer_key() -> KeyFile:
    """One demo key, created on first run and reused thereafter."""
    WORK.mkdir(parents=True, exist_ok=True)
    if not KEYFILE.exists():
        KeyFile.generate().save(KEYFILE)
    return KeyFile.load(KEYFILE)


def _token() -> str:
    return secrets.token_hex(6)


def _save_upload(storage) -> Path:
    suffix = Path(storage.filename or "").suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError(f"unsupported file type '{suffix or 'none'}'. "
                         f"Upload a PNG, JPG, BMP, TIFF or PDF.")
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"in_{_token()}{suffix}"
    storage.save(path)
    return path


def _preview(pages: list[np.ndarray], stem: str) -> tuple[str, float]:
    """Write a browser-displayable PNG of page 1.

    Returns its URL and the factor mapping preview pixels back to document
    pixels, so a click on the preview can be turned into a real coordinate.
    """
    img = pages[0]
    pil = Image.fromarray(img, "L" if img.ndim == 2 else "RGB")
    scale = 1.0
    if pil.width > 1100:
        scale = pil.width / 1100
        pil = pil.resize((1100, round(pil.height / scale)), Image.LANCZOS)
    name = f"{stem}_preview.png"
    pil.save(WORK / name)
    return f"/files/{name}", scale


def _check_size(pages: list[np.ndarray]) -> None:
    total = sum(p.shape[0] * p.shape[1] for p in pages)
    if total > MAX_PIXELS:
        raise ValueError(f"document is too large ({total/1e6:.0f} megapixels); "
                         f"the demo caps at {MAX_PIXELS//10**6}.")


@app.errorhandler(Exception)
def on_error(exc):
    if isinstance(exc, ValueError):
        return jsonify(error=str(exc)), 400
    traceback.print_exc()
    return jsonify(error=f"{type(exc).__name__}: {exc}"), 500


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/files/<path:name>")
def files(name):
    return send_from_directory(WORK, name)


@app.post("/api/protect")
def api_protect():
    """Watermark an uploaded document and attach its QR anchor."""
    if "file" not in request.files or not request.files["file"].filename:
        raise ValueError("no file was uploaded")
    kf = issuer_key()
    src = _save_upload(request.files["file"])
    carrier = request.form.get("carrier", "dct")
    pages_in = docio.load_pages(src)
    _check_size(pages_in)

    params = Params(carrier=carrier)
    token = _token()
    out_name = f"protected_{token}{'.pdf' if docio.is_pdf(src) else '.png'}"
    rendered, info = [], []

    for page in pages_in:
        res = embed(page, kf.hmac_key, params, signing_key=kf.sign_sk,
                    note=request.form.get("note", "")[:40])
        if not res.converged:
            raise ValueError("embedding could not reach a self-consistent state "
                             "for this image; try the LSB carrier.")
        composed, ecc, version = readable_qr(
            res.manifest, lambda qr: docio.attach_qr(res.image, qr))
        rendered.append(composed)
        info.append({"doc_id": res.manifest.doc_id,
                     "fragments": res.manifest.params.n_fragments,
                     "psnr": round(res.psnr, 2), "rounds": res.rounds,
                     "grid": f"{res.manifest.params.grid_rows} x "
                             f"{res.manifest.params.grid_cols}",
                     "qr": f"v{version}/{ecc}"})

    docio.save_pages(WORK / out_name, rendered)
    (WORK / "current.txt").write_text(out_name)
    preview, scale = _preview(rendered, f"protected_{token}")
    return jsonify(ok=True, pages=info, carrier=carrier, preview=preview,
                   preview_scale=scale, download=f"/files/{out_name}",
                   filename=out_name)


@app.post("/api/tamper")
def api_tamper():
    """Forge the document currently held, at a position chosen at random."""
    marker = WORK / "current.txt"
    if not marker.exists():
        raise ValueError("protect a document first")
    src = WORK / marker.read_text().strip()
    if not src.exists():
        raise ValueError("the protected document is no longer available")

    pages = docio.load_pages(src)
    body = request.json or {}
    text = body.get("text", "VOID")[:24] or "VOID"

    if body.get("x") is not None and body.get("y") is not None:
        # The operator picked the spot. Keep it inside the authenticated
        # region: a forgery landing on the QR strip would destroy the anchor
        # rather than the document, which demonstrates nothing.
        w, h = _authenticated_extent(pages[0])
        rw, rh = 190, 54
        x = max(0, min(int(body["x"]) - rw // 2, w - rw))
        y = max(0, min(int(body["y"]) - rh // 2, h - rh))
        rect, chosen = (x, y, rw, rh), "clicked"
    else:
        rect, chosen = _random_rect(pages[0], None), "random"

    pages[0] = attacks.write_text(pages[0], rect, text)
    token = _token()
    out_name = f"forged_{token}{src.suffix}"
    docio.save_pages(WORK / out_name, pages)
    preview, scale = _preview(pages, f"forged_{token}")
    return jsonify(ok=True, rect=list(rect), text=text, chosen=chosen,
                   preview=preview, preview_scale=scale,
                   download=f"/files/{out_name}", filename=out_name)


@app.post("/api/verify")
def api_verify():
    """Authenticate an uploaded document and localise any tampering."""
    if "file" not in request.files or not request.files["file"].filename:
        raise ValueError("no file was uploaded")
    kf = issuer_key()
    src = _save_upload(request.files["file"])
    pages = docio.load_pages(src)
    _check_size(pages)

    results, maps = [], []
    for i, page in enumerate(pages):
        try:
            manifest = read_qr(page)
        except ValueError:
            raise ValueError(
                "no QR anchor was found on this document. Upload a file that "
                "was protected here -- an unprotected original has nothing to "
                "check against."
            ) from None

        region, _ = docio.crop_authenticated(page, manifest.width, manifest.height)
        res = verify(region, manifest, kf.hmac_key, issuer_key=kf.sign_pk)
        overlay = report.overlay(region, res, manifest.params.fragment)
        name = f"map_{_token()}_p{i}.png"
        pil = Image.fromarray(overlay, "RGB")
        if pil.width > 1100:
            pil = pil.resize((1100, round(pil.height * 1100 / pil.width)), Image.LANCZOS)
        pil.save(WORK / name)
        maps.append(f"/files/{name}")

        results.append({
            "page": i + 1,
            "verdict": res.verdict,
            "authentic": res.authentic,
            "doc_id": manifest.doc_id,
            "fragments": res.n_fragments,
            "tampered": res.n_tampered,
            "fallout": res.n_mismatch - res.n_tampered,
            "ratio": round(res.tampered_ratio * 100, 2),
            "root_ok": res.root_ok,
            "signature_ok": res.signature_ok,
            "cells": np.argwhere(res.tampered).tolist()[:12],
            "issued_at": manifest.issued_at,
            "note": manifest.note,
            "map": maps[-1],
        })

    return jsonify(ok=True, pages=results,
                   authentic=all(r["authentic"] for r in results))


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    issuer_key()
    print("\n  QLFW demo running at  http://127.0.0.1:5005\n")
    app.run(host="127.0.0.1", port=5005, debug=False)
