"""Embedding and verification: the two operations the whole scheme exists for."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

import numpy as np

from . import crypto, docio, transform as T
from .carriers import get_carrier
from .config import Params
from .manifest import Manifest

MAX_ROUNDS = 8


def _bits(raw: bytes, n: int) -> np.ndarray:
    return np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:n]


def _bytes(bits: np.ndarray) -> bytes:
    return np.packbits(bits.astype(np.uint8)).tobytes()


def psnr(a: np.ndarray, b: np.ndarray) -> float:
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return float("inf") if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


@dataclass
class EmbedResult:
    image: np.ndarray
    manifest: Manifest
    rounds: int
    psnr: float
    converged: bool


def embed(image: np.ndarray, key: bytes, params: Params, *,
          doc_id: str | None = None, signing_key: bytes | None = None,
          note: str = "") -> EmbedResult:
    """Watermark ``image`` and produce the QR manifest that anchors it."""
    carrier = get_carrier(params.carrier)
    if carrier.capacity(params.fragment) < params.tag_bits:
        raise ValueError(
            f"a {params.fragment}px fragment carries only "
            f"{carrier.capacity(params.fragment)} bits with the {params.carrier} "
            f"carrier, but tag_bits={params.tag_bits}. Raise --fragment or lower --tag-bits."
        )

    work = image
    if params.carrier == "dct" and work.ndim == 3:
        # Grayscale keeps every authenticated byte inside the plane the carrier
        # controls; chroma would otherwise be unprotected.
        work = docio.to_gray(work)
    work = T.pad_to_grid(work, params.fragment)

    rows, cols = T.fragment_grid(work.shape[0], work.shape[1], params.fragment)
    params = params.with_grid(rows, cols)
    n = params.n_fragments
    doc_id = doc_id or secrets.token_hex(8)
    perm = crypto.dispersal(key, doc_id, n)

    base = carrier.prepare(work, params)
    payload = np.zeros((n, params.tag_bits), dtype=np.uint8)
    out, tags, rounds, converged = work, [], 0, False

    # Fixed-point search. A fragment's digest is read back from the *rendered*
    # uint8 image, so the document we ship is one we have actually verified
    # against itself rather than one we assume is self-consistent.
    for rounds in range(1, MAX_ROUNDS + 1):
        out = carrier.render(base, payload, params)
        digests = carrier.digests(out, params)
        tags = [crypto.fragment_tag(key, doc_id, i, digests[i], params.tag_bits)
                for i in range(n)]
        nxt = np.zeros_like(payload)
        for i, tag in enumerate(tags):
            nxt[perm[i]] = _bits(tag, params.tag_bits)
        if np.array_equal(nxt, payload):
            converged = True
            break
        payload = nxt

    manifest = Manifest(
        doc_id=doc_id, width=out.shape[1], height=out.shape[0],
        params=params, merkle_root=crypto.merkle_root(tags), note=note,
    )
    if signing_key:
        manifest.sign_with(signing_key)

    return EmbedResult(out, manifest, rounds, psnr(work, out), converged)


@dataclass
class VerifyResult:
    verdict: str
    root_ok: bool
    signature_ok: bool | None
    mismatch: np.ndarray            # (rows, cols) bool: tag check failed
    tampered: np.ndarray            # (rows, cols) bool: refined localisation
    bit_errors: np.ndarray          # (rows, cols) int: Hamming distance per tag
    n_fragments: int
    tolerance: int
    notes: list[str] = field(default_factory=list)

    @property
    def n_mismatch(self) -> int:
        return int(self.mismatch.sum())

    @property
    def n_tampered(self) -> int:
        return int(self.tampered.sum())

    @property
    def tampered_ratio(self) -> float:
        return self.n_tampered / self.n_fragments if self.n_fragments else 0.0

    @property
    def authentic(self) -> bool:
        return self.verdict == "AUTHENTIC"


def verify(image: np.ndarray, manifest: Manifest, key: bytes, *,
           issuer_key: bytes | None = None,
           tolerance: int | None = None) -> VerifyResult:
    """Check a document against its QR manifest and localise any tampering.

    ``issuer_key`` is the Ed25519 public key the verifier expects the anchor to
    be signed by. Without it the pixels can still be authenticated -- that is
    what the HMAC key is for -- but the document's origin cannot be, and the
    result says so rather than implying more than it checked.
    """
    p = manifest.params
    carrier = get_carrier(p.carrier)
    notes: list[str] = []
    if tolerance is None:
        # The fragile carrier admits no slack; the semi-fragile one must tolerate
        # a few QIM slips from recompression without crying forgery.
        tolerance = 0 if p.carrier == "lsb" else p.tag_bits // 8

    work = image
    if p.carrier == "dct" and work.ndim == 3:
        work = docio.to_gray(work)

    if work.shape[:2] != (manifest.height, manifest.width):
        notes.append(
            f"geometry mismatch: manifest describes {manifest.width}x{manifest.height}, "
            f"got {work.shape[1]}x{work.shape[0]} -- the document was cropped, "
            f"resized or re-rendered, so fragment alignment is lost"
        )
        shape = (p.grid_rows, p.grid_cols)
        return VerifyResult(
            verdict="UNVERIFIABLE", root_ok=False,
            signature_ok=manifest.signature_ok(issuer_key),
            mismatch=np.ones(shape, bool), tampered=np.ones(shape, bool),
            bit_errors=np.full(shape, p.tag_bits), n_fragments=p.n_fragments,
            tolerance=tolerance, notes=notes,
        )

    n = p.n_fragments
    perm = crypto.dispersal(key, manifest.doc_id, n)
    digests = carrier.digests(work, p)
    extracted = carrier.extract(work, p)

    expected = [crypto.fragment_tag(key, manifest.doc_id, i, digests[i], p.tag_bits)
                for i in range(n)]
    errors = np.empty(n, dtype=np.int32)
    for i, tag in enumerate(expected):
        recovered = extracted[perm[i]][: p.tag_bits]
        errors[i] = int(np.count_nonzero(recovered != _bits(tag, p.tag_bits)))

    mismatch = errors > tolerance

    # A fragment that fails may be innocent: it also fails when the *guardian*
    # holding its tag was the thing edited. Keep only fragments whose own
    # guardian relationship is consistent with them being the edited one, which
    # strips most of that halo off the tamper map.
    inv = np.empty(n, dtype=np.int64)
    inv[np.asarray(perm)] = np.arange(n)
    tampered = mismatch & mismatch[inv] if n > 1 else mismatch.copy()
    if mismatch.any() and not tampered.any():
        tampered = mismatch.copy()  # never report "something changed, nowhere"

    root_ok = crypto.merkle_root(expected) == manifest.merkle_root
    sig_ok = manifest.signature_ok(issuer_key)
    if sig_ok is None:
        reason = ("the document was issued unsigned" if not manifest.signature
                  else "no expected issuer key was supplied")
        notes.append(f"origin not checked ({reason}): this result speaks to "
                     f"integrity, not provenance")
    # A false result needs no note: the verdict line already states it.

    if sig_ok is False:
        # Say what was observed, not what it implies. An unexpected signature
        # is equally consistent with a forged anchor and with a verifier
        # holding the wrong key file, and only one of those is an accusation.
        verdict = "UNTRUSTED_ANCHOR"
        if mismatch.all():
            notes.append("every fragment also failed, so the likeliest "
                         "explanation is a key file that does not belong to "
                         "this document rather than a forgery")
    elif root_ok and not mismatch.any():
        verdict = "AUTHENTIC"
    elif mismatch.all():
        verdict = "WRONG_KEY_OR_REPLACED"
        notes.append("every fragment failed: either the verification key is wrong "
                     "or the document is not the one the QR describes")
    else:
        verdict = "TAMPERED"

    shape = (p.grid_rows, p.grid_cols)
    return VerifyResult(
        verdict=verdict, root_ok=root_ok, signature_ok=sig_ok,
        mismatch=mismatch.reshape(shape), tampered=tampered.reshape(shape),
        bit_errors=errors.reshape(shape), n_fragments=n,
        tolerance=tolerance, notes=notes,
    )
