"""End-to-end integration tests over the HTTP API.

These exercise the whole claim of the system: that a protected document
verifies as authentic, that a single-region edit is detected *and localised*,
and that stripping the authentication furniture does not make a forgery pass.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.sample_docs import build_certificate

API = "/api/v1"


@pytest.fixture(scope="module")
def certificate(tmp_root: Path) -> Path:
    return build_certificate(tmp_root / "source-certificate.pdf")


@pytest.fixture(scope="module")
def issued(client, admin_headers, certificate: Path) -> dict:
    with open(certificate, "rb") as handle:
        response = client.post(
            f"{API}/documents",
            headers=admin_headers,
            files={"file": ("degree-certificate.pdf", handle, "application/pdf")},
            params={"subject": "Aarav Sharma", "issuer": "Test University"},
        )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(scope="module")
def secured_pdf(client, admin_headers, issued, tmp_root: Path) -> Path:
    response = client.get(f"{API}/documents/{issued['id']}/download", headers=admin_headers)
    assert response.status_code == 200
    path = tmp_root / "secured.pdf"
    path.write_bytes(response.content)
    return path


def verify(client, path: Path, **data) -> dict:
    with open(path, "rb") as handle:
        response = client.post(
            f"{API}/verify",
            files={"file": (path.name, handle, "application/pdf")},
            data=data or None,
        )
    assert response.status_code == 200, response.text
    return response.json()


def tamper(client, admin_headers, document_id: str, tmp_root: Path, **payload) -> Path:
    response = client.post(
        f"{API}/documents/{document_id}/tamper-sandbox", headers=admin_headers, json=payload
    )
    assert response.status_code == 200, response.text
    path = tmp_root / f"tampered-{payload.get('mode')}-{payload.get('cell_index', 'x')}.pdf"
    path.write_bytes(response.content)
    return path


class TestAuth:
    def test_login_returns_a_usable_token_pair(self, client):
        response = client.post(
            f"{API}/auth/login",
            json={"email": "admin@docauth.dev", "password": "Admin@12345"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["user"]["role"] == "admin"
        assert body["access_token"] and body["refresh_token"]

    def test_bad_password_is_rejected(self, client):
        response = client.post(
            f"{API}/auth/login", json={"email": "admin@docauth.dev", "password": "nope"}
        )
        assert response.status_code == 401

    def test_refresh_token_cannot_be_used_as_an_access_token(self, client):
        tokens = client.post(
            f"{API}/auth/login",
            json={"email": "admin@docauth.dev", "password": "Admin@12345"},
        ).json()
        response = client.get(
            f"{API}/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
        )
        assert response.status_code == 401

    def test_self_registration_cannot_grant_admin(self, client):
        response = client.post(
            f"{API}/auth/register",
            json={
                "name": "Escalating User",
                "email": "escalate@example.com",
                "password": "Password@123",
                "role": "admin",
            },
        )
        assert response.status_code == 201
        assert response.json()["user"]["role"] == "verifier"

    def test_admin_routes_reject_verifiers(self, client):
        tokens = client.post(
            f"{API}/auth/register",
            json={
                "name": "Plain Verifier",
                "email": "plain@example.com",
                "password": "Password@123",
            },
        ).json()
        response = client.get(
            f"{API}/documents", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )
        assert response.status_code == 403


class TestProtection:
    def test_issued_document_has_fragments_root_and_signature(self, issued):
        assert issued["status"] == "active"
        assert len(issued["merkle_root"]) == 64
        assert issued["fragment_count"] == issued["grid_rows"] * issued["grid_cols"] * issued[
            "page_count"
        ]
        assert len(issued["fragments"]) == issued["fragment_count"]
        assert issued["signature"]

    def test_fragments_carry_geometry_for_localisation(self, issued):
        for fragment in issued["fragments"]:
            assert fragment["x1"] > fragment["x0"]
            assert fragment["y1"] > fragment["y0"]
            assert len(fragment["fragment_hash"]) == 64

    def test_non_pdf_upload_is_refused(self, client, admin_headers):
        response = client.post(
            f"{API}/documents",
            headers=admin_headers,
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert response.status_code == 415


class TestAuthenticVerification:
    def test_untouched_document_verifies_as_authentic(self, client, secured_pdf):
        result = verify(client, secured_pdf)
        assert result["result"] == "authentic"
        assert result["tamper_score"] == 0.0
        assert result["signature"]["valid"]
        assert result["merkle"]["match"]
        assert result["watermark"]["valid"]
        assert result["fragments"]["modified"] == 0
        assert result["fragments"]["marker_issues"] == 0
        assert result["heatmap"] == []

    def test_qr_is_recovered_optically_from_the_footer(self, client, secured_pdf):
        result = verify(client, secured_pdf)
        assert result["qr"]["found"]
        assert result["qr"]["payload"]["merkle_root"] == result["merkle"]["signed_root"]

    def test_verification_is_logged_and_reportable(self, client, secured_pdf):
        result = verify(client, secured_pdf)
        log_id = result["log_id"]
        assert client.get(f"{API}/verify/logs/{log_id}").status_code == 200
        report = client.get(f"{API}/verify/logs/{log_id}/report")
        assert report.status_code == 200
        assert report.content.startswith(b"%PDF")

    def test_qr_payload_can_be_validated_on_its_own(self, client, secured_pdf, issued):
        from app.services import pdf_builder

        raw = pdf_builder.extract_footer_qr_payloads(secured_pdf)
        assert raw, "QR should be optically readable"
        response = client.post(f"{API}/verify/qr", json={"raw": raw[0]})
        assert response.status_code == 200
        body = response.json()
        assert body["verdict"] == "valid"
        assert body["signature_valid"] and body["root_matches_register"]
        assert body["document"]["id"] == issued["id"]


class TestTamperDetection:
    @pytest.mark.parametrize("cell_index", [2, 6, 8])
    def test_a_text_edit_is_detected_in_exactly_that_cell(
        self, client, admin_headers, issued, tmp_root, cell_index
    ):
        path = tamper(
            client,
            admin_headers,
            issued["id"],
            tmp_root,
            mode="edit_text",
            page_index=0,
            cell_index=cell_index,
            replacement="Second Class - Pass",
        )
        result = verify(client, path)

        assert result["result"] == "tampered"
        assert result["tamper_score"] > 0
        assert not result["merkle"]["match"]
        # The signature is still genuine: the attacker edited the body, not the
        # signed root. That is precisely why fragment hashing is needed.
        assert result["signature"]["valid"]
        assert result["fragments"]["modified"] == 1
        offenders = [
            f["cell_index"] for f in result["fragments"]["analysis"] if f["status"] != "intact"
        ]
        assert offenders == [cell_index]
        assert [r["cell_index"] for r in result["heatmap"]] == [cell_index]

    def test_the_tampered_region_reports_why(self, client, admin_headers, issued, tmp_root):
        path = tamper(
            client,
            admin_headers,
            issued["id"],
            tmp_root,
            mode="edit_text",
            page_index=0,
            cell_index=4,
        )
        result = verify(client, path)
        region = next(f for f in result["fragments"]["analysis"] if f["status"] == "modified")
        assert region["text_changed"] or region["visual_changed"]
        assert region["marker_status"] in ("mismatch", "absent")
        assert region["expected_hash"] != region["actual_hash"]
        assert region["box"]["nx1"] <= 1.0 and region["box"]["ny1"] <= 1.0

    def test_a_redaction_block_is_detected_even_without_text_change(
        self, client, admin_headers, issued, tmp_root
    ):
        path = tamper(
            client,
            admin_headers,
            issued["id"],
            tmp_root,
            mode="overlay_block",
            page_index=0,
            cell_index=3,
        )
        result = verify(client, path)
        assert result["result"] == "tampered"
        offender = next(f for f in result["fragments"]["analysis"] if f["status"] != "intact")
        assert offender["visual_changed"], "raster hashing should catch a painted-over region"

    def test_stripping_the_footer_does_not_produce_a_pass(
        self, client, admin_headers, issued, tmp_root
    ):
        path = tamper(
            client, admin_headers, issued["id"], tmp_root, mode="strip_watermark", page_index=0
        )
        result = verify(client, path)
        assert result["result"] != "authentic"
        assert not result["watermark"]["valid"] or not result["qr"]["found"]

    def test_page_removal_is_detected(self, client, admin_headers, tmp_root, certificate):
        from app.services.sample_docs import build_transcript

        # A two-page document, so one page can be removed.
        merged = tmp_root / "two-page.pdf"
        import pypdf

        writer = pypdf.PdfWriter()
        for source in (certificate, build_transcript(tmp_root / "transcript.pdf")):
            for page in pypdf.PdfReader(str(source)).pages:
                writer.add_page(page)
        with open(merged, "wb") as handle:
            writer.write(handle)

        with open(merged, "rb") as handle:
            response = client.post(
                f"{API}/documents",
                headers=admin_headers,
                files={"file": ("two-page.pdf", handle, "application/pdf")},
            )
        assert response.status_code == 201
        document = response.json()
        assert document["page_count"] == 2

        path = tamper(
            client, admin_headers, document["id"], tmp_root, mode="replace_page", page_index=1
        )
        result = verify(client, path)
        assert result["result"] == "tampered"
        assert result["fragments"]["missing"] == document["grid_rows"] * document["grid_cols"]

    def test_an_unprotected_pdf_is_reported_as_unknown(self, client, tmp_root, certificate):
        result = verify(client, certificate)
        assert result["result"] == "unknown"
        assert not result["qr"]["found"]
        assert not result["manifest_present"]
        assert result["document"]["status"] == "unprotected"


class TestRevocation:
    def test_a_revoked_document_fails_verification_then_recovers(
        self, client, admin_headers, issued, secured_pdf
    ):
        response = client.post(
            f"{API}/documents/{issued['id']}/revoke",
            headers=admin_headers,
            json={"reason": "Superseded by a corrected certificate"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "revoked"

        result = verify(client, secured_pdf)
        assert result["result"] == "revoked"
        assert result["revoked"] is True
        # Integrity is untouched: the file is genuine, the authority withdrew it.
        assert result["merkle"]["match"] and result["fragments"]["modified"] == 0

        assert (
            client.post(
                f"{API}/documents/{issued['id']}/reinstate", headers=admin_headers
            ).json()["status"]
            == "active"
        )
        assert verify(client, secured_pdf)["result"] == "authentic"


class TestDashboards:
    def test_stats_cover_totals_and_a_time_series(self, client, admin_headers):
        response = client.get(f"{API}/dashboard/stats", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["totals"]["documents"] >= 1
        assert body["totals"]["verification_requests"] >= 1
        assert len(body["series"]) == body["window_days"] + 1
        assert {"date", "issued", "authentic", "tampered"} <= set(body["series"][0])

    def test_tamper_hotspots_rank_the_targeted_cells(self, client, admin_headers):
        response = client.get(f"{API}/dashboard/tamper-hotspots", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["hotspots"]

    def test_audit_trail_records_issuance_and_verification(self, client, admin_headers):
        response = client.get(f"{API}/audit-logs", headers=admin_headers)
        assert response.status_code == 200
        actions = {entry["action"] for entry in response.json()["items"]}
        assert "document.protect" in actions or "document.verify" in actions

    def test_public_key_is_published(self, client):
        response = client.get(f"{API}/verify/public-key")
        assert response.status_code == 200
        assert "BEGIN PUBLIC KEY" in response.json()["public_pem"]
