"""Watermark carriers: where the fragmented tags physically live in the pixels.

Every carrier guarantees a clean split of the pixel data into

* **payload coefficients** -- modified to carry tag bits, and
* **digest coefficients** -- never modified, and snapped onto a quantisation
  lattice during embedding so they survive the uint8 round-trip exactly.

That split is what makes the scheme computable at all: the digest a fragment is
authenticated by does not depend on the bits written into it.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import numpy as np

from . import transform as T
from .config import Params

# --- DCT carrier coefficient layout (zig-zag neighbours, disjoint sets) -----

#: Mid-band coefficients that carry payload bits. Low enough to survive mild
#: JPEG recompression, high enough to stay invisible.
WM_COEFFS = ((1, 2), (2, 1), (2, 2), (1, 3))

#: DC plus the lowest AC coefficients, with their lattice steps. These describe
#: a fragment's coarse appearance -- any edit that changes what a human reads
#: moves them, while recompression noise does not. The step has to exceed twice
#: the worst drift an embed-then-quantise round-trip can cause, or a digest
#: would depend on the payload and the scheme would not close.
HASH_COEFFS = (((0, 0), 16.0), ((0, 1), 16.0), ((1, 0), 16.0),
               ((0, 2), 16.0), ((2, 0), 16.0))

#: Safety band kept clear at both ends of the pixel range, as a multiple of the
#: QIM step. A document page is mostly saturated white with black text, and a
#: saturated block has no room to be modulated: the clip on the way back to
#: uint8 simply erases the payload. Compressing the tonal range first buys that
#: room back. The cost is a background a shade off pure white.
HEADROOM_FACTOR = 1.0


class Carrier(Protocol):
    name: str

    def capacity(self, fragment: int) -> int: ...
    def prepare(self, img: np.ndarray, p: Params) -> np.ndarray: ...
    def render(self, base: np.ndarray, payload: np.ndarray, p: Params) -> np.ndarray: ...
    def extract(self, img: np.ndarray, p: Params) -> np.ndarray: ...
    def digests(self, img: np.ndarray, p: Params) -> list[bytes]: ...


def _hash_rows(rows: np.ndarray) -> list[bytes]:
    """SHA-256 each row of an integer matrix, one digest per fragment."""
    raw = np.ascontiguousarray(rows.astype(np.int32)).tobytes()
    stride = rows.shape[1] * 4
    return [hashlib.sha256(raw[i * stride:(i + 1) * stride]).digest()
            for i in range(rows.shape[0])]


def _fragment_view(grid: np.ndarray, p: Params) -> np.ndarray:
    """(GH, GW, ...) sub-block grid -> (n_fragments, k, k, ...) grouped by fragment."""
    k = p.fragment // T.B
    gh, gw = grid.shape[:2]
    tail = grid.shape[2:]
    return (grid.reshape(gh // k, k, gw // k, k, *tail)
                .swapaxes(1, 2)
                .reshape(gh // k * (gw // k), k, k, *tail))


class DctCarrier:
    """Semi-fragile quantisation-index-modulation carrier on the luminance DCT.

    Operates on grayscale: documents are tonally flat, and dropping chroma keeps
    every authenticated byte inside the one plane the carrier controls.
    """

    name = "dct"

    def capacity(self, fragment: int) -> int:
        return (fragment // T.B) ** 2 * len(WM_COEFFS)

    @staticmethod
    def headroom(strength: float) -> int:
        """Gray levels to keep clear at each end so modulation is not clipped."""
        return int(np.ceil(HEADROOM_FACTOR * strength))

    def prepare(self, img: np.ndarray, p: Params) -> np.ndarray:
        """Return the DCT coefficient grid, ready to be modulated.

        Two preparations happen here, both of which the verifier knows nothing
        about because it only ever reads the delivered pixels: the tonal range
        is compressed to leave modulation headroom, and the digest coefficients
        are snapped onto their lattice so that quantisation noise cannot move
        them into a neighbouring bucket.
        """
        if img.ndim == 3:
            raise ValueError("DCT carrier expects a grayscale plane")
        head = self.headroom(p.strength)
        plane = head + img.astype(np.float64) * (255.0 - 2 * head) / 255.0
        coeffs = T.dct2(T.to_subblocks(plane))
        for (u, v), q in HASH_COEFFS:
            level = np.round(coeffs[:, :, u, v] / q)
            if (u, v) == (0, 0):
                # Keep the block mean inside the representable range, or the
                # snap itself would push a white block past 255 and be clipped.
                limit = np.floor((255.0 - head) * T.B / q)
                level = np.clip(level, np.ceil(head * T.B / q), limit)
            coeffs[:, :, u, v] = level * q
        return coeffs

    def render(self, base: np.ndarray, payload: np.ndarray, p: Params) -> np.ndarray:
        coeffs = base.copy()
        k = p.fragment // T.B
        gh, gw = coeffs.shape[:2]
        # payload (n_fragments, bits) -> one bit per (sub-block, coefficient)
        bits = payload.reshape(-1, k, k, len(WM_COEFFS))
        bits = (bits.reshape(gh // k, gw // k, k, k, len(WM_COEFFS))
                    .swapaxes(1, 2)
                    .reshape(gh, gw, len(WM_COEFFS)))
        for i, (u, v) in enumerate(WM_COEFFS):
            coeffs[:, :, u, v] = _qim_embed(coeffs[:, :, u, v], bits[:, :, i], p.strength)
        plane = T.from_subblocks(T.idct2(coeffs))
        return np.clip(np.round(plane), 0, 255).astype(np.uint8)

    def extract(self, img: np.ndarray, p: Params) -> np.ndarray:
        coeffs = T.dct2(T.to_subblocks(img.astype(np.float64)))
        k = p.fragment // T.B
        gh, gw = coeffs.shape[:2]
        bits = np.stack(
            [_qim_decode(coeffs[:, :, u, v], p.strength) for u, v in WM_COEFFS],
            axis=-1,
        )
        return (bits.reshape(gh // k, k, gw // k, k, len(WM_COEFFS))
                    .swapaxes(1, 2)
                    .reshape(gh // k * (gw // k), -1))

    def digests(self, img: np.ndarray, p: Params) -> list[bytes]:
        coeffs = T.dct2(T.to_subblocks(img.astype(np.float64)))
        levels = np.stack(
            [np.round(coeffs[:, :, u, v] / q) for (u, v), q in HASH_COEFFS], axis=-1
        )
        per_fragment = _fragment_view(levels, p)
        return _hash_rows(per_fragment.reshape(per_fragment.shape[0], -1))


def _qim_embed(c: np.ndarray, bit: np.ndarray, step: float) -> np.ndarray:
    """Dither modulation: snap each coefficient to the lattice meaning ``bit``."""
    d = np.where(bit.astype(bool), 0.25, -0.25) * step
    return np.round((c - d) / step) * step + d


def _qim_decode(c: np.ndarray, step: float) -> np.ndarray:
    """Recover the bit by nearest lattice point -- robust to small drift."""
    cand = [np.round((c - d) / step) * step + d
            for d in (-0.25 * step, 0.25 * step)]
    return (np.abs(c - cand[1]) < np.abs(c - cand[0])).astype(np.uint8)


class LsbCarrier:
    """Fragile least-significant-bit carrier. Exact, colour-safe, zero slack.

    Any change to the file at all -- one pixel, one recompression -- is caught.
    Use it for born-digital documents that are never re-encoded.
    """

    name = "lsb"

    def capacity(self, fragment: int) -> int:
        return fragment * fragment

    def prepare(self, img: np.ndarray, p: Params) -> np.ndarray:
        return img  # nothing to stabilise: bit 0 and bits 1..7 are independent

    def _positions(self, p: Params) -> tuple[np.ndarray, np.ndarray]:
        """Spread the tag bits evenly across the fragment rather than bunching
        them in the top rows, so the distortion is uniform."""
        stride = (p.fragment * p.fragment) // p.tag_bits
        flat = np.arange(p.tag_bits) * stride
        return flat // p.fragment, flat % p.fragment

    def render(self, base: np.ndarray, payload: np.ndarray, p: Params) -> np.ndarray:
        out = base.copy()
        chan = out[..., -1] if out.ndim == 3 else out
        rr, cc = self._positions(p)
        cols = base.shape[1] // p.fragment
        idx = np.arange(payload.shape[0])
        r0 = (idx // cols) * p.fragment
        c0 = (idx % cols) * p.fragment
        chan[(r0[:, None] + rr)[:, :], (c0[:, None] + cc)[:, :]] = (
            chan[(r0[:, None] + rr), (c0[:, None] + cc)] & 0xFE
        ) | payload
        return out

    def extract(self, img: np.ndarray, p: Params) -> np.ndarray:
        chan = img[..., -1] if img.ndim == 3 else img
        rr, cc = self._positions(p)
        cols = img.shape[1] // p.fragment
        n = (img.shape[0] // p.fragment) * cols
        idx = np.arange(n)
        r0 = (idx // cols) * p.fragment
        c0 = (idx % cols) * p.fragment
        return (chan[(r0[:, None] + rr), (c0[:, None] + cc)] & 1).astype(np.uint8)

    def digests(self, img: np.ndarray, p: Params) -> list[bytes]:
        stripped = img & 0xFE  # bit 0 is ours; everything else is the content
        if stripped.ndim == 2:
            stripped = stripped[..., None]
        tiles = (stripped.reshape(img.shape[0] // p.fragment, p.fragment,
                                  img.shape[1] // p.fragment, p.fragment, -1)
                         .swapaxes(1, 2))
        flat = tiles.reshape(-1, p.fragment * p.fragment * stripped.shape[-1])
        return _hash_rows(flat)


CARRIERS: dict[str, Carrier] = {c.name: c for c in (DctCarrier(), LsbCarrier())}


def get_carrier(name: str) -> Carrier:
    try:
        return CARRIERS[name]
    except KeyError:
        raise ValueError(f"unknown carrier {name!r}; choose from {sorted(CARRIERS)}") from None
