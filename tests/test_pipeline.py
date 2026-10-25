import numpy as np
import pytest

from qlfw import tamper
from qlfw.config import Params
from qlfw.manifest import Manifest
from qlfw.pipeline import embed, verify


def _check(res, keys, manifest=None, **kw):
    """Verify as a relying party would: with the issuer key named up front."""
    return verify(res, manifest, keys.hmac_key, issuer_key=keys.sign_pk, **kw)


def _issue(page, keys, params, **kw):
    res = embed(page, keys.hmac_key, params, signing_key=keys.sign_sk, **kw)
    assert res.converged, (
        f"{params.carrier}: embedding never reached a self-consistent state "
        f"({res.rounds} rounds) -- digests must not depend on the payload"
    )
    return res


def test_clean_document_verifies(page, keys, params):
    res = _issue(page, keys, params)
    out = _check(res.image, keys, res.manifest)
    assert out.verdict == "AUTHENTIC"
    assert out.root_ok and out.signature_ok is True
    assert out.n_mismatch == 0, "an untouched document must raise no flags at all"


def test_watermark_is_near_invisible(page, keys, params):
    res = _issue(page, keys, params)
    floor = 40.0 if params.carrier == "lsb" else 25.0
    assert res.psnr > floor, f"PSNR {res.psnr:.1f} dB is too low for {params.carrier}"


def test_tampering_is_detected_and_localised(page, keys, params):
    """Localisation is a recall guarantee with a bounded precision cost.

    The dispersal makes a stray unavoidable in principle: when an edited
    fragment's own guardian was also inside the edit, a third fragment gets
    promoted. Measured over 400 random keys the edit was never missed, strays
    averaged 0.2 and never exceeded 2, so that is what is asserted -- a
    zero-stray assertion would be flaky about one run in five.
    """
    res = _issue(page, keys, params)
    forged = tamper.blank(res.image, (96, 128, 64, 64))  # fragments rows 4-5, cols 3-4
    out = _check(forged, keys, res.manifest)

    assert out.verdict == "TAMPERED"
    assert not out.root_ok

    found = {tuple(c) for c in np.argwhere(out.tampered).tolist()}
    truth = {(r, c) for r in (4, 5) for c in (3, 4)}
    assert found & truth, f"the edit was not localised at all; got {sorted(found)}"
    assert len(found - truth) <= 2, (
        f"false positives outside the edit: {sorted(found - truth)}"
    )


def test_single_fragment_edit_is_caught(page, keys, params):
    res = _issue(page, keys, params)
    forged = res.image.copy()
    if params.carrier == "lsb":
        forged[40, 40] ^= 0x10          # one pixel, one bit of content
    else:
        forged[32:64, 32:64] = 128      # one fragment repainted
    out = _check(forged, keys, res.manifest)
    assert out.verdict == "TAMPERED"
    assert out.tampered[1, 1], "the edited fragment itself must be flagged"


def test_splice_within_the_same_page_is_caught(page, keys, params):
    """Position-bound tags are what defeat copy-and-paste: moved pixels carry an
    authenticator computed for the index they came from."""
    res = _issue(page, keys, params)
    forged = tamper.splice(res.image, src=(32, 32), rect=(32, 160, 64, 64))
    out = _check(forged, keys, res.manifest)
    assert out.verdict == "TAMPERED"
    assert out.tampered.any()


def test_wrong_key_cannot_verify(page, keys, params):
    res = _issue(page, keys, params)
    out = verify(res.image, res.manifest, b"\x00" * 32, issuer_key=keys.sign_pk)
    assert out.verdict == "WRONG_KEY_OR_REPLACED"
    assert not out.root_ok


def test_altered_qr_anchor_is_rejected(page, keys, params):
    """Re-anchoring the page to a different commitment must not pass as a mere
    content edit: the signature is what distinguishes the two."""
    res = _issue(page, keys, params)
    hijacked = Manifest.decode(res.manifest.encode())
    hijacked.merkle_root = b"\x00" * 32
    out = _check(res.image, keys, hijacked)
    assert out.verdict == "UNTRUSTED_ANCHOR"
    assert out.signature_ok is False


def test_unsigned_document_reports_integrity_but_not_origin(page, keys, params):
    res = embed(page, keys.hmac_key, params)
    assert res.converged
    out = verify(res.image, res.manifest, keys.hmac_key, issuer_key=keys.sign_pk)
    assert out.verdict == "AUTHENTIC" and out.signature_ok is None
    assert any("origin not checked" in n for n in out.notes)


def test_a_verifier_that_names_no_issuer_is_told_so(page, keys, params):
    res = _issue(page, keys, params)
    out = verify(res.image, res.manifest, keys.hmac_key)
    assert out.verdict == "AUTHENTIC"
    assert out.signature_ok is None, "an unasked question must not read as a pass"
    assert any("no expected issuer" in n for n in out.notes)


def test_resized_document_is_unverifiable_not_authentic(page, keys, params):
    res = _issue(page, keys, params)
    out = _check(res.image[:-32, :-32], keys, res.manifest)
    assert out.verdict == "UNVERIFIABLE"
    assert not out.authentic


def test_dct_carrier_survives_mild_jpeg(page, keys):
    """The semi-fragile carrier must tell benign recompression apart from an edit."""
    res = _issue(page, keys, Params(carrier="dct"))
    out = _check(tamper.jpeg(res.image, quality=92), keys, res.manifest)
    assert out.tampered_ratio < 0.05, (
        f"JPEG q92 flagged {out.tampered_ratio:.1%} of the page as tampered"
    )


def test_lsb_carrier_is_fragile_by_design(page, keys):
    res = _issue(page, keys, Params(carrier="lsb"))
    out = _check(tamper.jpeg(res.image, quality=95), keys, res.manifest)
    assert not out.authentic, "the fragile carrier must reject any recompression"


def test_tamper_still_stands_out_after_jpeg(page, keys):
    """Recompressing the forgery must not hide it, nor swamp it in noise.

    A couple of stray cells are expected and tolerated: the dispersal
    refinement promotes a guardian fragment whenever its own guardian was also
    inside the edit. What must not happen is losing the real region.
    """
    res = _issue(page, keys, Params(carrier="dct"))
    forged = tamper.jpeg(tamper.blank(res.image, (96, 128, 64, 64)), quality=92)
    out = _check(forged, keys, res.manifest)

    found = {tuple(c) for c in np.argwhere(out.tampered).tolist()}
    truth = {(r, c) for r in (4, 5) for c in (3, 4)}
    assert truth <= found, f"lost part of the edit: missed {sorted(truth - found)}"
    assert len(found - truth) <= 2, f"too many strays: {sorted(found - truth)}"


def test_dct_breakdown_point_is_where_it_is_documented(page, keys):
    """Pin the claim the README makes: clean at JPEG q92, degraded by q85.

    This is the scheme's real limit, so it is a test rather than a footnote.
    """
    res = _issue(page, keys, Params(carrier="dct"))
    clean = _check(tamper.jpeg(res.image, quality=92), keys, res.manifest)
    assert clean.n_mismatch == 0, "q92 must be entirely clean"
    broken = _check(tamper.jpeg(res.image, quality=85), keys, res.manifest)
    assert broken.verdict == "WRONG_KEY_OR_REPLACED", (
        "below the breakdown point the carrier must fail loudly, not quietly "
        "report a plausible-looking partial tamper map"
    )


def test_colour_input_works_on_both_carriers(keys, params):
    rng = np.random.default_rng(3)
    page = np.full((160, 160, 3), 240, np.uint8)
    page[40:120, 40:120] = rng.integers(20, 90, (80, 80, 3))
    res = _issue(page, keys, params)
    assert _check(res.image, keys, res.manifest).verdict == "AUTHENTIC"


def test_lsb_authenticates_chroma(keys):
    """Colour-only edits must not slip through the colour-capable carrier."""
    page = np.full((128, 128, 3), 200, np.uint8)
    res = _issue(page, keys, Params(carrier="lsb"))
    forged = res.image.copy()
    forged[32:64, 32:64, 0] = 120          # red channel only
    assert _check(forged, keys, res.manifest).verdict == "TAMPERED"


def test_padding_leaves_no_unauthenticated_margin(keys, params):
    page = np.full((100, 70), 220, np.uint8)   # neither side is a multiple of 32
    res = _issue(page, keys, params)
    assert res.manifest.height == 128 and res.manifest.width == 96
    forged = res.image.copy()
    forged[res.manifest.height - 8:, res.manifest.width - 8:] = 0  # inside the pad
    assert _check(forged, keys, res.manifest).verdict == "TAMPERED"


def test_capacity_shortfall_is_an_error_not_a_silent_truncation(page, keys):
    with pytest.raises(ValueError, match="carries only"):
        embed(page, keys.hmac_key, Params(carrier="dct", fragment=16, tag_bits=64))


def test_fragment_must_tile_dct_blocks():
    with pytest.raises(ValueError, match="multiple of 8"):
        Params(fragment=20)
