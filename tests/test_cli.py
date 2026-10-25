import json

import numpy as np
import pytest
from PIL import Image

from qlfw import docio
from qlfw.cli import main
from qlfw.manifest import Manifest
from qlfw.keystore import KeyFile


@pytest.fixture
def workspace(tmp_path, page):
    kf = tmp_path / "issuer.key"
    assert main(["keygen", "--out", str(kf)]) == 0
    src = tmp_path / "doc.png"
    Image.fromarray(page, "L").save(src)
    return tmp_path, kf, src


def test_keygen_refuses_to_clobber_a_live_key(workspace):
    _, kf, _ = workspace
    before = kf.read_text()
    assert main(["keygen", "--out", str(kf)]) == 1
    assert kf.read_text() == before, "an existing key must never be overwritten"
    assert main(["keygen", "--out", str(kf), "--force"]) == 0
    assert kf.read_text() != before


def test_keyfile_is_not_world_readable(workspace):
    _, kf, _ = workspace
    assert kf.stat().st_mode & 0o077 == 0


def test_embed_then_verify_from_the_attached_qr_alone(workspace):
    tmp, kf, src = workspace
    out = tmp / "wm.png"
    assert main(["embed", str(src), str(out), "--keyfile", str(kf)]) == 0
    # Delete the sidecar so verification has to read the QR off the page.
    (tmp / "wm.qlfw").unlink()
    assert main(["verify", str(out), "--keyfile", str(kf)]) == 0


def test_verify_exit_code_reports_tampering(workspace, capsys):
    tmp, kf, src = workspace
    out, forged = tmp / "wm.png", tmp / "forged.png"
    assert main(["embed", str(src), str(out), "--keyfile", str(kf)]) == 0
    assert main(["tamper", str(out), str(forged), "--mode", "blank",
                 "--rect", "96,128,64,64"]) == 0
    capsys.readouterr()

    assert main(["verify", str(forged), "--keyfile", str(kf), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["verdict"] == "TAMPERED"
    assert payload[0]["tampered_cells"], "the report must name the fragments"
    assert payload[0]["signature_ok"] is True


def test_tamper_map_marks_the_edited_region(workspace):
    tmp, kf, src = workspace
    out, forged, tmap = tmp / "wm.png", tmp / "forged.png", tmp / "map.png"
    main(["embed", str(src), str(out), "--keyfile", str(kf)])
    main(["tamper", str(out), str(forged), "--mode", "blank", "--rect", "96,128,64,64"])
    main(["verify", str(forged), "--keyfile", str(kf), "--map", str(tmap)])

    overlay = np.array(Image.open(tmap).convert("RGB")).astype(int)
    reddish = (overlay[..., 0] - overlay[..., 2]) > 40
    assert reddish[128:192, 96:160].mean() > 0.9, "the edit must be tinted"
    assert reddish[:96, :].mean() < 0.25, "the untouched header must stay mostly clean"


def test_expect_issuer_rejects_a_document_from_another_signer(workspace, tmp_path):
    tmp, kf, src = workspace
    out = tmp / "wm.png"
    main(["embed", str(src), str(out), "--keyfile", str(kf)])
    stranger = KeyFile.generate().sign_pk.hex()
    assert main(["verify", str(out), "--keyfile", str(kf),
                 "--expect-issuer", stranger]) == 1
    assert main(["verify", str(out), "--keyfile", str(kf), "--expect-issuer",
                 KeyFile.load(kf).sign_pk.hex()]) == 0


def test_inspect_reads_the_manifest_without_the_secret_key(workspace, capsys):
    tmp, kf, src = workspace
    out = tmp / "wm.png"
    main(["embed", str(src), str(out), "--keyfile", str(kf), "--note", "registrar"])
    capsys.readouterr()
    issuer = KeyFile.load(kf).sign_pk.hex()
    assert main(["inspect", str(out), "--issuer", issuer]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["note"] == "registrar" and info["signed"] is True
    assert "expected issuer" in info["signature"]
    assert info["fragments"] > 0


def test_inspect_flags_a_signature_from_the_wrong_issuer(workspace, capsys):
    tmp, kf, src = workspace
    out = tmp / "wm.png"
    main(["embed", str(src), str(out), "--keyfile", str(kf)])
    capsys.readouterr()
    assert main(["inspect", str(out), "--issuer",
                 KeyFile.generate().sign_pk.hex()]) == 1
    assert "NOT signed" in capsys.readouterr().out


def test_refuses_to_write_a_watermarked_jpeg(workspace, capsys):
    tmp, kf, src = workspace
    assert main(["embed", str(src), str(tmp / "wm.jpg"), "--keyfile", str(kf)]) == 2
    assert "JPEG" in capsys.readouterr().err


def test_multipage_pdf_round_trip_and_per_page_localisation(workspace, capsys):
    tmp, kf, _ = workspace
    rng = np.random.default_rng(1)
    pages = [np.full((256, 192), 240, np.uint8) for _ in range(2)]
    for p in pages:
        p[60:160, 30:160] = rng.integers(20, 90, (100, 130))
    src = tmp / "two.pdf"
    docio.save_pages(src, pages)

    out, forged = tmp / "two.wm.pdf", tmp / "two.forged.pdf"
    assert main(["embed", str(src), str(out), "--keyfile", str(kf)]) == 0
    assert main(["verify", str(out), "--keyfile", str(kf)]) == 0

    assert main(["tamper", str(out), str(forged), "--mode", "blank",
                 "--rect", "64,64,32,32", "--page", "2"]) == 0
    capsys.readouterr()
    assert main(["verify", str(forged), "--keyfile", str(kf), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report[0]["verdict"] == "AUTHENTIC", "page 1 was untouched"
    assert report[1]["verdict"] == "TAMPERED"
    assert [2, 2] in report[1]["tampered_cells"]


def test_pdf_raster_round_trip_is_bit_exact(tmp_path):
    """The whole PDF path rests on this: any resampling destroys the tags."""
    rng = np.random.default_rng(0)
    page = rng.integers(0, 256, (320, 256), dtype=np.uint8)
    path = tmp_path / "x.pdf"
    docio.save_pages(path, [page])
    back = docio.to_gray(docio.load_pages(path)[0])
    assert np.array_equal(back, page)


def test_odd_dpi_is_snapped_rather_than_silently_resampling():
    assert docio.normalise_dpi(200) in docio.PDF_DPI_CHOICES
    assert docio.normalise_dpi(150) == 144


def test_a_refused_output_path_leaves_nothing_behind(workspace):
    """Failing late would strand a manifest describing a document that does
    not exist, which a later verify would happily pick up."""
    tmp, kf, src = workspace
    assert main(["embed", str(src), str(tmp / "wm.jpg"), "--keyfile", str(kf)]) == 2
    assert not list(tmp.glob("*.qlfw")), "an orphan manifest was left behind"


def test_random_attacks_stay_inside_the_authenticated_region(workspace, capsys):
    """A random target that lands on the QR strip destroys the anchor instead
    of the document -- a different experiment, and a confusing one to run live.
    """
    tmp, kf, src = workspace
    out = tmp / "wm.png"
    main(["embed", str(src), str(out), "--keyfile", str(kf)])
    manifest = Manifest.decode((tmp / "wm.qlfw").read_text())
    capsys.readouterr()

    for seed in range(25):
        forged = tmp / f"f{seed}.png"
        assert main(["tamper", str(out), str(forged), "--mode", "text",
                     "--rect", "random", "--seed", str(seed)]) == 0
        capsys.readouterr()
        # The anchor must still be readable, and the edit must still be found.
        assert main(["verify", str(forged), "--keyfile", str(kf), "--json"]) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["verdict"] == "TAMPERED", f"seed {seed}"
        for row, col in payload[0]["tampered_cells"]:
            assert row < manifest.params.grid_rows and col < manifest.params.grid_cols
