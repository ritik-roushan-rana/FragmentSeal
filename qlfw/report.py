"""Human-facing output: the tamper map overlay and the console verdict."""

from __future__ import annotations

import numpy as np

from .pipeline import VerifyResult

TAMPERED_RGB = (220, 38, 38)      # fragments the evidence points at
SUSPECT_RGB = (245, 158, 11)      # failed, but likely guardian fallout
ALPHA = 0.45

_VERDICT_STYLE = {
    "AUTHENTIC": ("\033[32m", "intact and signed by the stated issuer"),
    "TAMPERED": ("\033[31m", "localised edits detected"),
    "UNTRUSTED_ANCHOR": ("\033[31m", "the QR anchor is not signed by the expected issuer"),
    "WRONG_KEY_OR_REPLACED": ("\033[31m", "not the document this QR describes"),
    "UNVERIFIABLE": ("\033[33m", "fragment alignment lost"),
}


def overlay(image: np.ndarray, result: VerifyResult, fragment: int,
            grid: bool = False) -> np.ndarray:
    """Tint tampered fragments red and guardian-fallout fragments amber."""
    rgb = np.repeat(image[..., None], 3, axis=2) if image.ndim == 2 else image.copy()
    rgb = rgb.astype(np.float32)

    suspect = result.mismatch & ~result.tampered
    for mask, colour in ((suspect, SUSPECT_RGB), (result.tampered, TAMPERED_RGB)):
        if not mask.any():
            continue
        # Expand the fragment-resolution mask to pixel resolution.
        pixels = np.kron(mask, np.ones((fragment, fragment), dtype=bool))
        pixels = pixels[: rgb.shape[0], : rgb.shape[1]]
        rgb[pixels] = rgb[pixels] * (1 - ALPHA) + np.array(colour, np.float32) * ALPHA

    out = np.clip(rgb, 0, 255).astype(np.uint8)
    if grid:
        out[::fragment, :] = out[::fragment, :] // 2 + 64
        out[:, ::fragment] = out[:, ::fragment] // 2 + 64
    return out


def _bar(ratio: float, width: int = 24) -> str:
    filled = int(round(ratio * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"


def format_result(result: VerifyResult, page: int | None = None) -> str:
    colour, gloss = _VERDICT_STYLE.get(result.verdict, ("\033[33m", ""))
    head = f"page {page}: " if page is not None else ""
    lines = [f"{head}{colour}{result.verdict}\033[0m  {gloss}"]

    sig = {True: "from the expected issuer",
           False: "NOT from the expected issuer",
           None: "not checked"}[result.signature_ok]
    lines.append(f"  merkle anchor : {'matches QR' if result.root_ok else 'does NOT match QR'}")
    lines.append(f"  issuer signature: {sig}")

    if result.verdict != "UNVERIFIABLE":
        lines.append(
            f"  fragments     : {result.n_tampered}/{result.n_fragments} tampered "
            f"({result.tampered_ratio:.1%}) {_bar(result.tampered_ratio)}"
        )
        halo = result.n_mismatch - result.n_tampered
        if halo:
            lines.append(f"  guardian fallout: {halo} fragment(s) flagged by dispersal, "
                         f"not themselves edited")
        if result.n_tampered:
            rows, cols = np.where(result.tampered)
            lines.append(f"  worst fragment: row {rows[0]}, col {cols[0]} "
                         f"({result.bit_errors[rows[0], cols[0]]}/"
                         f"{result.bit_errors.max()} bit errors)")
            lines.append(f"  bit-error tolerance in use: {result.tolerance}")
    for note in result.notes:
        lines.append(f"  note: {note}")
    return "\n".join(lines)
