"""Semi-fragile DWT watermarking.

A bit payload derived from the document's Merkle root is embedded into the
mid-frequency wavelet coefficients of a carrier image using quantisation index
modulation (QIM). The carrier is stamped into the reserved footer band of every
page of the secured PDF; extraction pulls the carrier back out of the PDF's
image XObjects and decodes the bits.

The scheme is *semi-fragile* by construction: the quantisation step tolerates
the small numeric error of an encode/decode round trip (and mild requantisation
or rescaling), but any substantive rewrite of the carrier destroys the payload,
so a stripped or forged stamp is detectable.

Coefficient positions are chosen by a key-derived pseudo-random permutation, so
an attacker cannot locate the carried bits without the key.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pywt
from PIL import Image

from app.core.config import settings

WM_IMAGE_KEY = "DocAuthWatermarkCarrier"


# --------------------------------------------------------------------------- #
# bit helpers
# --------------------------------------------------------------------------- #
def hex_to_bits(hex_string: str, n_bits: int) -> list[int]:
    raw = bytes.fromhex(hex_string)
    bits: list[int] = []
    for byte in raw:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
            if len(bits) == n_bits:
                return bits
    while len(bits) < n_bits:  # pad deterministically by rehashing
        raw = hashlib.sha256(raw).digest()
        for byte in raw:
            for shift in range(7, -1, -1):
                bits.append((byte >> shift) & 1)
                if len(bits) == n_bits:
                    return bits
    return bits[:n_bits]


def bits_to_hex(bits: list[int]) -> str:
    padded = bits + [0] * (-len(bits) % 8)
    out = bytearray()
    for i in range(0, len(padded), 8):
        value = 0
        for bit in padded[i : i + 8]:
            value = (value << 1) | bit
        out.append(value)
    return out.hex()


def bit_error_rate(a: list[int], b: list[int]) -> float:
    if not a or len(a) != len(b):
        return 1.0
    return sum(1 for x, y in zip(a, b) if x != y) / len(a)


# --------------------------------------------------------------------------- #
# carrier
# --------------------------------------------------------------------------- #
def make_carrier(seed: str, width: int | None = None, height: int | None = None) -> np.ndarray:
    """Deterministic low-contrast carrier texture (float array, 0-255)."""
    width = width or settings.CARRIER_W
    height = height or settings.CARRIER_H
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big"))
    ys, xs = np.mgrid[0:height, 0:width]
    gradient = 206.0 + 14.0 * np.sin(xs / 11.0) + 8.0 * np.cos(ys / 7.0)
    noise = rng.normal(0.0, 3.0, size=(height, width))
    return np.clip(gradient + noise, 150.0, 245.0)


def _positions(key: str, count: int, total: int) -> np.ndarray:
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big"))
    return rng.permutation(total)[:count]


# --------------------------------------------------------------------------- #
# embed / extract
# --------------------------------------------------------------------------- #
def embed_bits(carrier: np.ndarray, bits: list[int], key: str) -> np.ndarray:
    """QIM-embed `bits` into the level-2 horizontal detail subband."""
    delta = settings.DWT_ALPHA
    coeffs = pywt.wavedec2(carrier, settings.DWT_WAVELET, level=2)
    cA, (cH2, cV2, cD2), level1 = coeffs[0], coeffs[1], coeffs[2]

    flat = cH2.flatten()
    if len(bits) > flat.size:
        raise ValueError(f"carrier holds {flat.size} bits, {len(bits)} requested")

    for bit, position in zip(bits, _positions(key, len(bits), flat.size)):
        step = np.floor(flat[position] / delta)
        if int(step) % 2 != bit:
            step += 1
        flat[position] = step * delta + delta / 2.0

    watermarked = pywt.waverec2(
        [cA, (flat.reshape(cH2.shape), cV2, cD2), level1], settings.DWT_WAVELET
    )
    watermarked = watermarked[: carrier.shape[0], : carrier.shape[1]]
    return np.clip(watermarked, 0, 255)


def extract_bits(carrier: np.ndarray, n_bits: int, key: str) -> list[int]:
    delta = settings.DWT_ALPHA
    coeffs = pywt.wavedec2(carrier.astype(np.float64), settings.DWT_WAVELET, level=2)
    flat = coeffs[1][0].flatten()
    bits: list[int] = []
    for position in _positions(key, n_bits, flat.size):
        bits.append(int(np.floor(flat[position] / delta)) % 2)
    return bits


def build_watermark_image(payload_hex: str, key: str) -> Image.Image:
    """Carrier PNG carrying the first DWT_BITS bits of `payload_hex`."""
    bits = hex_to_bits(payload_hex, settings.DWT_BITS)
    carrier = make_carrier(key)
    stamped = embed_bits(carrier, bits, key)
    return Image.fromarray(np.round(stamped).astype(np.uint8), mode="L")


def verify_watermark_image(
    image: Image.Image, payload_hex: str, key: str, tolerance: float = 0.08
) -> dict:
    """Compare bits recovered from `image` against the expected payload."""
    expected = hex_to_bits(payload_hex, settings.DWT_BITS)
    recovered = extract_bits(np.asarray(image.convert("L"), dtype=np.float64), len(expected), key)
    ber = bit_error_rate(expected, recovered)
    return {
        "valid": ber <= tolerance,
        "bit_error_rate": round(ber, 4),
        "bits_checked": len(expected),
        "bits_matched": len(expected) - int(round(ber * len(expected))),
        "expected_prefix": bits_to_hex(expected)[:16],
        "recovered_prefix": bits_to_hex(recovered)[:16],
        "tolerance": tolerance,
    }
