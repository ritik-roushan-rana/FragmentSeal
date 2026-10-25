import numpy as np
import pytest

from qlfw import crypto, docio
from qlfw.config import Params
from qlfw.manifest import (SAFE_QR_VERSION, Manifest, read_qr, readable_qr,
                           to_qr_image)


def _manifest(**kw) -> Manifest:
    return Manifest(doc_id="abc1230000000000", width=256, height=320,
                    params=Params().with_grid(10, 8),
                    merkle_root=b"\x07" * 32, **kw)


def test_encode_decode_round_trip():
    m = _manifest(note="registrar")
    back = Manifest.decode(m.encode())
    assert back.doc_id == m.doc_id and back.note == "registrar"
    assert back.merkle_root == m.merkle_root
    assert back.params == m.params
    assert back.issued_at == m.issued_at


def test_fragment_grid_is_derived_not_stored():
    """Keeping it out of the record is how the record stays small enough to read."""
    back = Manifest.decode(_manifest().encode())
    assert (back.params.grid_rows, back.params.grid_cols) == (10, 8)


def test_signature_checks_against_a_caller_supplied_key():
    sk, pk = crypto.generate_keypair()
    m = _manifest()
    m.sign_with(sk)
    assert m.signature_ok(pk) is True
    assert m.signature_ok(crypto.generate_keypair()[1]) is False
    assert m.signature_ok(None) is None, "no expected issuer means the question is unasked"


def test_signature_covers_every_field_that_matters():
    sk, pk = crypto.generate_keypair()
    for field, value in [("merkle_root", b"\x08" * 32), ("note", "altered"),
                         ("width", 288), ("doc_id", "ffffffffffffffff"),
                         ("issued_at", "2001-01-01T00:00:00+00:00")]:
        m = _manifest(note="original")
        m.sign_with(sk)
        setattr(m, field, value)
        assert m.signature_ok(pk) is False, f"{field} is not covered by the signature"


def test_signature_survives_the_wire():
    sk, pk = crypto.generate_keypair()
    m = _manifest(note="registrar")
    m.sign_with(sk)
    assert Manifest.decode(m.encode()).signature_ok(pk) is True


def test_unsigned_manifest_reports_none():
    assert _manifest().signature_ok(crypto.generate_keypair()[1]) is None


def test_record_stays_small_enough_to_decode_reliably():
    """The format's whole shape is justified by this bound; hold it to it."""
    sk, _ = crypto.generate_keypair()
    m = _manifest(note="NGU-2022-04417")
    m.sign_with(sk)
    _, version = to_qr_image(m)
    assert version <= SAFE_QR_VERSION + 2, (
        f"QR grew to version {version}; commodity decoders get flaky past "
        f"v{SAFE_QR_VERSION}"
    )


def test_readable_qr_guarantees_the_composed_page_decodes():
    sk, _ = crypto.generate_keypair()
    doc = np.full((320, 256), 250, np.uint8)
    for seed in range(12):
        rng = np.random.default_rng(seed)
        m = _manifest(note="NGU-2022-04417")
        m.doc_id = rng.integers(0, 256, 8, dtype=np.uint8).tobytes().hex()
        m.merkle_root = rng.integers(0, 256, 32, dtype=np.uint8).tobytes()
        m.sign_with(sk)
        page, ecc, _ = readable_qr(m, lambda qr: docio.attach_qr(doc, qr))
        assert read_qr(page).doc_id == m.doc_id, f"seed {seed} shipped an unreadable anchor"


def test_decode_rejects_foreign_and_damaged_payloads():
    for bad in ["https://example.com/not-a-manifest", "QLFW:AAAA", "QLFW:"]:
        with pytest.raises(ValueError):
            Manifest.decode(bad)


def test_decode_rejects_dimensions_that_do_not_tile():
    m = _manifest()
    m.width = 250  # not a multiple of the 32px fragment
    with pytest.raises(ValueError, match="tile"):
        Manifest.decode(m.encode())
