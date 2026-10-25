"""Command line interface: qlfw keygen | embed | verify | inspect | tamper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from . import docio, report, tamper as attacks
from .config import DEFAULT_FRAGMENT, DEFAULT_TAG_BITS, Params
from .keystore import KeyFile
from .manifest import (SAFE_QR_VERSION, Manifest, read_qr, readable_qr,
                       to_qr_image)
from .pipeline import embed, verify


def _sidecar(path: Path, page: int, pages: int) -> Path:
    stem = f"{path.stem}.p{page + 1}" if pages > 1 else path.stem
    return path.with_name(f"{stem}.qlfw")


# --- keygen -----------------------------------------------------------------

def cmd_keygen(args) -> int:
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"{out} already exists; pass --force to overwrite and "
              f"PERMANENTLY invalidate every document issued with it",
              file=sys.stderr)
        return 1
    kf = KeyFile.generate()
    kf.save(out)
    print(f"wrote {out} (mode 0600)")
    print(f"issuer public key: {kf.sign_pk.hex()}")
    print("keep this file secret: it is the verification key, not just a signing key")
    return 0


# --- embed ------------------------------------------------------------------

def cmd_embed(args) -> int:
    docio.check_output_path(args.output)
    kf = KeyFile.load(args.keyfile)
    params = Params(fragment=args.fragment, tag_bits=args.tag_bits,
                    carrier=args.carrier, strength=args.strength)
    pages = docio.load_pages(args.input, dpi=args.dpi)
    out_path = Path(args.output)
    rendered, failures = [], 0

    for i, page in enumerate(pages):
        res = embed(page, kf.hmac_key, params,
                    signing_key=None if args.unsigned else kf.sign_sk,
                    note=args.note)
        if not res.converged:
            failures += 1
            print(f"page {i + 1}: embedding did not reach a self-consistent "
                  f"state in {res.rounds} rounds -- refusing to ship it",
                  file=sys.stderr)
            continue

        compose = ((lambda qr: res.image) if args.no_attach
                   else (lambda qr: docio.attach_qr(res.image, qr)))
        composed, ecc, version = readable_qr(res.manifest, compose, box=args.qr_box)
        rendered.append(composed)

        side = _sidecar(out_path, i, len(pages))
        side.parent.mkdir(parents=True, exist_ok=True)
        side.write_text(res.manifest.encode() + "\n")
        if args.qr_out:
            qp = Path(args.qr_out)
            qr, _ = to_qr_image(res.manifest, box=args.qr_box, ecc=ecc)
            docio.save_image(_sidecar(qp, i, len(pages)).with_suffix(qp.suffix), qr)

        print(f"page {i + 1}/{len(pages)}: {res.manifest.params.n_fragments} fragments "
              f"({params.fragment}px), PSNR {res.psnr:.2f} dB, "
              f"converged in {res.rounds} round(s)")
        print(f"            doc id {res.manifest.doc_id}  "
              f"QR v{version}/{ecc}  manifest -> {side}")
        if version > SAFE_QR_VERSION:
            print(f"            note: QR symbol version {version} is denser than "
                  f"v{SAFE_QR_VERSION}; it reads back here, but shortening --note "
                  f"would leave more margin on a photographed page")

    if failures or not rendered:
        return 1
    docio.save_pages(out_path, rendered, dpi=args.dpi)
    print(f"wrote {out_path}")
    return 0


# --- verify -----------------------------------------------------------------

def _load_manifest(page: np.ndarray, args, index: int, total: int) -> Manifest:
    if args.manifest:
        text = Path(args.manifest).read_text().strip()
        return Manifest.decode(text)
    side = _sidecar(Path(args.input), index, total)
    try:
        return read_qr(page)
    except ValueError:
        if side.exists():
            return Manifest.decode(side.read_text().strip())
        raise


def cmd_verify(args) -> int:
    kf = KeyFile.load(args.keyfile)
    # The issuer key is supplied by the verifier, never taken from the document.
    try:
        issuer = (bytes.fromhex(args.expect_issuer) if args.expect_issuer
                  else kf.sign_pk)
    except ValueError:
        print("error: --expect-issuer must be a 64-character hex public key",
              file=sys.stderr)
        return 2
    if len(issuer) != 32:
        print("error: --expect-issuer must be a 32-byte (64 hex char) key",
              file=sys.stderr)
        return 2

    pages = docio.load_pages(args.input, dpi=args.dpi)
    results, overlays = [], []

    for i, page in enumerate(pages):
        try:
            manifest = _load_manifest(page, args, i, len(pages))
        except ValueError as exc:
            print(f"page {i + 1}: cannot read a manifest ({exc}); "
                  f"pass --manifest to supply it", file=sys.stderr)
            return 2

        region, cropped = docio.crop_authenticated(page, manifest.width, manifest.height)
        res = verify(region, manifest, kf.hmac_key, issuer_key=issuer,
                     tolerance=args.tolerance)
        if cropped:
            res.notes.append("cropped the attached QR strip before checking pixels")

        results.append((manifest, res))
        if args.map:
            src = region if region.ndim == page.ndim else region
            overlays.append(report.overlay(src, res, manifest.params.fragment,
                                           grid=args.grid))
        if not args.json:
            print(report.format_result(res, page=i + 1 if len(pages) > 1 else None))

    if args.map and overlays:
        docio.save_pages(args.map, overlays, dpi=args.dpi)
        if not args.json:
            print(f"tamper map -> {args.map}")

    if args.json:
        print(json.dumps([{
            "page": i + 1,
            "doc_id": m.doc_id,
            "verdict": r.verdict,
            "authentic": r.authentic,
            "merkle_root_ok": r.root_ok,
            "signature_ok": r.signature_ok,
            "expected_issuer": issuer.hex(),
            "fragments": r.n_fragments,
            "tampered": r.n_tampered,
            "flagged": r.n_mismatch,
            "tampered_ratio": round(r.tampered_ratio, 6),
            "tolerance": r.tolerance,
            "tampered_cells": np.argwhere(r.tampered).tolist(),
            "notes": r.notes,
        } for i, (m, r) in enumerate(results)], indent=2))

    return 0 if all(r.authentic for _, r in results) else 1


# --- inspect ----------------------------------------------------------------

def cmd_inspect(args) -> int:
    source = Path(args.input)
    if source.suffix.lower() in (".txt", ".qlfw"):
        manifest = Manifest.decode(source.read_text().strip())
    else:
        manifest = read_qr(docio.load_pages(source, dpi=args.dpi)[0])
    info = manifest.summary()
    issuer = bytes.fromhex(args.issuer) if args.issuer else None
    checked = manifest.signature_ok(issuer)
    info["signature"] = {True: "signed by the expected issuer",
                         False: "NOT signed by the expected issuer",
                         None: ("unsigned" if not manifest.signature
                                else "present, but no --issuer given to check it")}[checked]
    print(json.dumps(info, indent=2))
    return 0 if checked is not False else 1


# --- tamper (demo utility) --------------------------------------------------

def _authenticated_extent(page: np.ndarray) -> tuple[int, int]:
    """Width and height of the region the watermark actually covers.

    The attached QR strip sits outside it. A random attack that lands there
    destroys the anchor rather than the document, which is a different
    experiment and a confusing one to run in front of an audience.
    """
    try:
        manifest = read_qr(page)
    except ValueError:
        return page.shape[1], page.shape[0]
    return min(manifest.width, page.shape[1]), min(manifest.height, page.shape[0])


def _random_rect(page: np.ndarray, seed: int | None) -> tuple[int, int, int, int]:
    """Pick a target the operator did not choose.

    Demonstrating this scheme with a fixed rectangle invites the obvious
    objection that the detector was tuned to it. It never sees the rectangle at
    all, and letting chance pick makes that visible rather than merely true.
    """
    rng = np.random.default_rng(seed)
    w, h = _authenticated_extent(page)
    rw = int(rng.integers(max(32, w // 8), max(40, w // 3)))
    rh = int(rng.integers(24, max(32, h // 10)))
    x = int(rng.integers(0, max(1, w - rw)))
    y = int(rng.integers(0, max(1, h - rh)))
    return x, y, min(rw, w - x), min(rh, h - y)


def cmd_tamper(args) -> int:
    pages = docio.load_pages(args.input, dpi=args.dpi)
    idx = args.page - 1
    if not 0 <= idx < len(pages):
        print(f"page {args.page} out of range (document has {len(pages)})", file=sys.stderr)
        return 1
    page = pages[idx]

    if args.mode in ("blank", "text", "splice") and not args.rect:
        print(f"--rect X,Y,W,H (or 'random') is required for --mode {args.mode}",
              file=sys.stderr)
        return 1

    if args.rect == "random":
        rect = _random_rect(page, args.seed)
        print(f"chose a random target: --rect {','.join(str(v) for v in rect)}")
    elif args.rect:
        try:
            rect = tuple(int(v) for v in args.rect.split(","))
            if len(rect) != 4:
                raise ValueError
        except ValueError:
            print("error: --rect must be X,Y,W,H or 'random'", file=sys.stderr)
            return 2
    else:
        rect = None

    if args.mode == "blank":
        page = attacks.blank(page, rect)
    elif args.mode == "text":
        page = attacks.write_text(page, rect, args.text)
    elif args.mode == "splice":
        if args.src == "random" or (args.rect == "random" and not args.src):
            sx, sy = _random_rect(page, None if args.seed is None
                                  else args.seed + 1)[:2]
            print(f"chose a random source: --src {sx},{sy}")
        elif args.src:
            sx, sy = (int(v) for v in args.src.split(","))
        else:
            print("error: --src X,Y (or 'random') is required for --mode splice",
                  file=sys.stderr)
            return 2
        page = attacks.splice(page, (sx, sy), rect)
    elif args.mode == "noise":
        page = attacks.noise(page, sigma=args.sigma)
    elif args.mode == "jpeg":
        page = attacks.jpeg(page, quality=args.quality)

    pages[idx] = page
    docio.save_pages(args.output, pages, dpi=args.dpi)
    print(f"applied '{args.mode}' to page {args.page} -> {args.output}")
    return 0


# --- argument wiring --------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qlfw",
        description="QR-linked fragmented watermarking for tamper-evident documents.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def shared(sp):
        sp.add_argument("--dpi", type=int, default=docio.DEFAULT_DPI,
                        choices=docio.PDF_DPI_CHOICES,
                        help="PDF rasterisation density; only these survive a "
                             "raster round-trip exactly (default: %(default)s)")

    k = sub.add_parser("keygen", help="create an issuer key file")
    k.add_argument("--out", default="issuer.key")
    k.add_argument("--force", action="store_true")
    k.set_defaults(func=cmd_keygen)

    e = sub.add_parser("embed", help="watermark a document and emit its QR anchor")
    e.add_argument("input")
    e.add_argument("output", help="output .png or .pdf")
    e.add_argument("--keyfile", required=True)
    e.add_argument("--carrier", choices=("dct", "lsb"), default="dct",
                   help="dct = semi-fragile, survives mild recompression; "
                        "lsb = fragile, catches any single-bit change")
    e.add_argument("--fragment", type=int, default=DEFAULT_FRAGMENT,
                   help="fragment side in pixels, multiple of 8 (default: %(default)s)")
    e.add_argument("--tag-bits", type=int, default=DEFAULT_TAG_BITS)
    e.add_argument("--strength", type=float, default=8.0,
                   help="QIM step: higher is more robust and more visible")
    e.add_argument("--note", default="", help="free text carried in the QR")
    e.add_argument("--unsigned", action="store_true",
                   help="omit the issuer signature (integrity only, no origin)")
    e.add_argument("--no-attach", action="store_true",
                   help="do not append the QR strip; write the QR separately")
    e.add_argument("--qr-out", help="also write the QR code to this image path")
    e.add_argument("--qr-box", type=int, default=4, help="QR module size in pixels")
    shared(e)
    e.set_defaults(func=cmd_embed)

    v = sub.add_parser("verify", help="authenticate a document and localise tampering")
    v.add_argument("input")
    v.add_argument("--keyfile", required=True)
    v.add_argument("--manifest", help="manifest text file, if the QR is unreadable")
    v.add_argument("--map", help="write a tamper-map overlay image/PDF here")
    v.add_argument("--grid", action="store_true", help="draw fragment boundaries on the map")
    v.add_argument("--tolerance", type=int, default=None,
                   help="bit errors allowed per fragment tag (default: carrier-dependent)")
    v.add_argument("--expect-issuer",
                   help="issuer public key to require, hex; defaults to the one "
                        "in --keyfile. The key is never read from the document")
    v.add_argument("--json", action="store_true")
    shared(v)
    v.set_defaults(func=cmd_verify)

    i = sub.add_parser("inspect", help="decode and print a QR manifest")
    i.add_argument("input", help="document, QR image, or .qlfw manifest file")
    i.add_argument("--issuer", help="issuer public key to check the signature "
                                    "against, hex")
    shared(i)
    i.set_defaults(func=cmd_inspect)

    t = sub.add_parser("tamper", help="simulate an attack, for demos and tests")
    t.add_argument("input")
    t.add_argument("output")
    t.add_argument("--mode", required=True,
                   choices=("blank", "text", "splice", "noise", "jpeg"))
    t.add_argument("--rect", help="X,Y,W,H target region, or 'random' to let "
                                  "chance pick one the detector never sees")
    t.add_argument("--src", help="X,Y source corner for --mode splice, or 'random'")
    t.add_argument("--seed", type=int, help="make a 'random' choice reproducible")
    t.add_argument("--text", default="TAMPERED", help="replacement text")
    t.add_argument("--page", type=int, default=1)
    t.add_argument("--sigma", type=float, default=2.0)
    t.add_argument("--quality", type=int, default=85)
    shared(t)
    t.set_defaults(func=cmd_tamper)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
