"""Vectorised 8x8 DCT over a whole image at once, plus fragment tiling."""

from __future__ import annotations

import numpy as np

B = 8  # DCT sub-block side


def _basis(n: int = B) -> np.ndarray:
    k = np.arange(n)
    m = np.cos((2 * k[None, :] + 1) * k[:, None] * np.pi / (2 * n))
    m *= np.sqrt(2.0 / n)
    m[0] *= np.sqrt(0.5)
    return m


_D = _basis().astype(np.float64)


def to_subblocks(plane: np.ndarray) -> np.ndarray:
    """(H, W) -> (H/8, W/8, 8, 8) view-like array of 8x8 tiles."""
    h, w = plane.shape
    if h % B or w % B:
        raise ValueError(f"plane {h}x{w} is not a multiple of {B}")
    return plane.reshape(h // B, B, w // B, B).swapaxes(1, 2)


def from_subblocks(tiles: np.ndarray) -> np.ndarray:
    """Inverse of :func:`to_subblocks`."""
    gh, gw = tiles.shape[:2]
    return tiles.swapaxes(1, 2).reshape(gh * B, gw * B)


def dct2(tiles: np.ndarray) -> np.ndarray:
    return _D @ tiles @ _D.T


def idct2(tiles: np.ndarray) -> np.ndarray:
    return _D.T @ tiles @ _D


def pad_to_grid(img: np.ndarray, fragment: int) -> np.ndarray:
    """Edge-replicate so the image tiles exactly into fragments.

    Padding rather than cropping keeps every original pixel inside an
    authenticated fragment -- there is no blind margin for a forger to hide in.
    """
    h, w = img.shape[:2]
    ph, pw = (-h) % fragment, (-w) % fragment
    if not ph and not pw:
        return img
    pad = ((0, ph), (0, pw)) + ((0, 0),) * (img.ndim - 2)
    return np.pad(img, pad, mode="edge")


def fragment_grid(h: int, w: int, fragment: int) -> tuple[int, int]:
    return h // fragment, w // fragment


def fragment_slice(index: int, cols: int, fragment: int) -> tuple[slice, slice]:
    r, c = divmod(index, cols)
    return (
        slice(r * fragment, (r + 1) * fragment),
        slice(c * fragment, (c + 1) * fragment),
    )
