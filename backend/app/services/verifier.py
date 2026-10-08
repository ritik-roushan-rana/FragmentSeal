"""The verification engine (verifier side).

Given an uploaded PDF it answers four independent questions and fuses them into
one verdict:

  1. Provenance  — is there a QR / embedded manifest, and does it name a
                   document this authority issued?
  2. Authority   — does the RSA-PSS signature over the claimed Merkle root
                   validate against a registered public key?
  3. Integrity   — do recomputed fragment hashes still rebuild that root, and
                   if not, *which* fragments moved?
  4. Watermark   — does the semi-fragile DWT payload still decode, and does each
                   region still carry its own matching marker?

Fragment-level comparison is what gives tamper *localisation*: every fragment
carries its grid geometry, so a mismatch maps straight back to a rectangle on
a page.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Document, DocumentStatus, Fragment, VerificationResult
from app.services import pdf_builder
from app.services.fragmenter import fragment_pdf, pdf_page_count
from app.services.merkle import MerkleTree, verify_proof
from app.services.qr import QRPayload
from app.services.signing import verify_root_signature
from app.services.watermark import verify_watermark_image

STATUS_INTACT = "intact"
STATUS_MODIFIED = "modified"
STATUS_MISSING = "missing"
STATUS_ADDED = "added"


@dataclass
class Baseline:
    """The trusted record a document is checked against."""

    source: str  # "database" | "manifest"
    document_id: str
    merkle_root: str
    signature: str
    key_id: str | None
    algorithm: str
    issued_at: str | None
    fragments: dict[tuple[int, int], dict] = field(default_factory=dict)
    order: list[tuple[int, int]] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# --------------------------------------------------------------------------- #
# evidence collection
# --------------------------------------------------------------------------- #
def collect_evidence(pdf_path: Path) -> dict:
    manifest = pdf_builder.read_manifest(pdf_path)
    qr_texts = pdf_builder.extract_footer_qr_payloads(pdf_path)
    qr_payload = None
    for text in qr_texts:
        qr_payload = QRPayload.from_json(text)
        if qr_payload:
            break
    return {
        "manifest": manifest,
        "qr_payload": qr_payload,
        "qr_found": qr_payload is not None,
        "qr_raw_count": len(qr_texts),
    }


def resolve_document(
    db: Session, qr_payload: QRPayload | None, manifest: dict | None, hint: str | None
) -> Document | None:
    for candidate in (
        qr_payload.document_id if qr_payload else None,
        (manifest or {}).get("document_id"),
        hint,
    ):
        if not candidate:
            continue
        document = db.get(Document, candidate)
        if document:
            return document
    return None


def baseline_from_document(db: Session, document: Document) -> Baseline:
    rows = list(
        db.scalars(
            select(Fragment)
            .where(Fragment.document_id == document.id)
            .order_by(Fragment.fragment_index)
        )
    )
    baseline = Baseline(
        source="database",
        document_id=document.id,
        merkle_root=document.merkle_root,
        signature=document.signature,
        key_id=document.key_id,
        algorithm=document.algorithm,
        issued_at=document.created_at.isoformat() if document.created_at else None,
    )
    for row in rows:
        key = (row.page_index, row.cell_index)
        baseline.fragments[key] = {
            "fragment_index": row.fragment_index,
            "fragment_hash": row.fragment_hash,
            "text_hash": row.text_hash,
            "raster_hash": row.raster_hash,
            "text_preview": row.text_preview,
            "char_count": row.char_count,
        }
        baseline.order.append(key)
    return baseline


def baseline_from_manifest(manifest: dict) -> Baseline:
    baseline = Baseline(
        source="manifest",
        document_id=str(manifest.get("document_id", "")),
        merkle_root=str(manifest.get("merkle_root", "")),
        signature=str(manifest.get("signature", "")),
        key_id=manifest.get("key_id"),
        algorithm=str(manifest.get("algorithm", "RSA-PSS-SHA256")),
        issued_at=manifest.get("issued_at"),
    )
    for entry in manifest.get("fragments", []):
        key = (int(entry["p"]), int(entry["c"]))
        baseline.fragments[key] = {
            "fragment_index": int(entry["i"]),
            "fragment_hash": str(entry["h"]),
            "text_hash": str(entry.get("t", "")),
            "raster_hash": "",
            "text_preview": "",
            "char_count": 0,
        }
        baseline.order.append(key)
    return baseline


# --------------------------------------------------------------------------- #
# fragment comparison
# --------------------------------------------------------------------------- #
def compare_fragments(baseline: Baseline, recomputed: list, markers: list[dict]) -> dict:
    marker_map = {(m["page_index"], m["cell_index"]): m["text_hash12"] for m in markers}
    current = {(f.page_index, f.cell_index): f for f in recomputed}

    analysis: list[dict] = []
    modified = missing = added = intact = 0
    marker_issues = 0

    for key in baseline.order:
        expected = baseline.fragments[key]
        page_index, cell_index = key
        found = current.get(key)

        if found is None:
            missing += 1
            analysis.append(
                {
                    "fragment_index": expected["fragment_index"],
                    "page_index": page_index,
                    "cell_index": cell_index,
                    "status": STATUS_MISSING,
                    "reason": "page or region no longer present in the document",
                    "expected_hash": expected["fragment_hash"],
                    "actual_hash": None,
                    "text_changed": True,
                    "visual_changed": True,
                    "marker_status": "absent",
                    "expected_preview": expected["text_preview"],
                    "actual_preview": "",
                    "box": None,
                }
            )
            continue

        text_changed = bool(expected["text_hash"]) and expected["text_hash"] != found.text_hash
        visual_changed = bool(expected["raster_hash"]) and expected["raster_hash"] != found.raster_hash
        hash_match = expected["fragment_hash"] == found.fragment_hash

        marker12 = marker_map.get(key)
        if marker12 is None:
            marker_status = "absent"
        elif marker12 == found.text_hash[:12]:
            marker_status = "valid"
        else:
            marker_status = "mismatch"
        if marker_status != "valid":
            marker_issues += 1

        if hash_match:
            intact += 1
            status = STATUS_INTACT
            reason = "fragment hash reproduces the issued value"
        else:
            modified += 1
            status = STATUS_MODIFIED
            parts = []
            if text_changed:
                parts.append("text content differs")
            if visual_changed:
                parts.append("rendered pixels differ")
            if not parts:
                parts.append("fragment digest differs")
            if marker_status == "mismatch":
                parts.append("embedded watermark marker does not match recomputed text")
            elif marker_status == "absent":
                parts.append("embedded watermark marker was stripped")
            reason = "; ".join(parts)

        analysis.append(
            {
                "fragment_index": expected["fragment_index"],
                "page_index": page_index,
                "cell_index": cell_index,
                "status": status,
                "reason": reason,
                "expected_hash": expected["fragment_hash"],
                "actual_hash": found.fragment_hash,
                "text_changed": text_changed,
                "visual_changed": visual_changed,
                "marker_status": marker_status,
                "expected_preview": expected["text_preview"],
                "actual_preview": found.text_preview,
                "box": {
                    "x0": found.x0,
                    "y0": found.y0,
                    "x1": found.x1,
                    "y1": found.y1,
                    "page_width": found.page_width,
                    "page_height": found.page_height,
                    "nx0": found.x0 / found.page_width,
                    "ny0": found.y0 / found.page_height,
                    "nx1": found.x1 / found.page_width,
                    "ny1": found.y1 / found.page_height,
                },
            }
        )

    for key, found in current.items():
        if key in baseline.fragments:
            continue
        added += 1
        analysis.append(
            {
                "fragment_index": -1,
                "page_index": key[0],
                "cell_index": key[1],
                "status": STATUS_ADDED,
                "reason": "region is not part of the issued document (page inserted?)",
                "expected_hash": None,
                "actual_hash": found.fragment_hash,
                "text_changed": True,
                "visual_changed": True,
                "marker_status": "absent",
                "expected_preview": "",
                "actual_preview": found.text_preview,
                "box": {
                    "x0": found.x0,
                    "y0": found.y0,
                    "x1": found.x1,
                    "y1": found.y1,
                    "page_width": found.page_width,
                    "page_height": found.page_height,
                    "nx0": found.x0 / found.page_width,
                    "ny0": found.y0 / found.page_height,
                    "nx1": found.x1 / found.page_width,
                    "ny1": found.y1 / found.page_height,
                },
            }
        )

    analysis.sort(key=lambda a: (a["page_index"], a["cell_index"]))
    return {
        "analysis": analysis,
        "intact": intact,
        "modified": modified,
        "missing": missing,
        "added": added,
        "marker_issues": marker_issues,
        "total": len(baseline.order),
    }


def heatmap_regions(analysis: list[dict]) -> list[dict]:
    severity = {STATUS_INTACT: 0.0, STATUS_MODIFIED: 1.0, STATUS_MISSING: 0.9, STATUS_ADDED: 0.7}
    regions = []
    for item in analysis:
        if item["status"] == STATUS_INTACT or not item["box"]:
            continue
        weight = severity.get(item["status"], 0.5)
        if item["status"] == STATUS_MODIFIED and item["text_changed"] and item["visual_changed"]:
            weight = 1.0
        elif item["status"] == STATUS_MODIFIED:
            weight = 0.75
        regions.append(
            {
                "page_index": item["page_index"],
                "cell_index": item["cell_index"],
                "status": item["status"],
                "severity": round(weight, 2),
                "reason": item["reason"],
                **item["box"],
            }
        )
    return regions


# --------------------------------------------------------------------------- #
# main entry point
# --------------------------------------------------------------------------- #
def verify_pdf(
    db: Session, pdf_path: Path, file_name: str, claimed_document_id: str | None = None
) -> dict:
    started = datetime.now(timezone.utc)
    timeline: list[dict] = []

    def step(name: str, ok: bool | None, detail: str) -> None:
        timeline.append(
            {
                "step": name,
                "ok": ok,
                "detail": detail,
                "at": datetime.now(timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z"),
            }
        )

    file_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    page_count = pdf_page_count(pdf_path)
    step("File received", True, f"{file_name} · {page_count} page(s) · sha256 {file_hash[:16]}…")

    evidence = collect_evidence(pdf_path)
    qr_payload: QRPayload | None = evidence["qr_payload"]
    manifest: dict | None = evidence["manifest"]
    step(
        "QR extraction",
        evidence["qr_found"],
        "QR payload decoded from the footer band"
        if evidence["qr_found"]
        else "no readable QR code found in the document footer",
    )
    step(
        "Embedded manifest",
        manifest is not None,
        "verification manifest recovered from PDF metadata"
        if manifest
        else "no embedded manifest present",
    )

    document = resolve_document(db, qr_payload, manifest, claimed_document_id)

    if document is None and manifest is None and qr_payload is None:
        step("Document lookup", False, "document carries no authentication data")
        return _unprotected_result(
            file_name, file_hash, page_count, timeline, started, claimed_document_id
        )

    if document is not None:
        baseline = baseline_from_document(db, document)
        step(
            "Document lookup",
            True,
            f"matched issued document '{document.document_name}' ({document.id})",
        )
    else:
        baseline = baseline_from_manifest(manifest or {})
        step(
            "Document lookup",
            False,
            "document id is not in the issuing register; falling back to the "
            "manifest embedded in the file (lower trust)",
        )

    claimed_root = (qr_payload.merkle_root if qr_payload else "") or baseline.merkle_root
    claimed_signature = (qr_payload.signature if qr_payload else "") or baseline.signature
    claimed_key_id = (qr_payload.key_id if qr_payload else None) or baseline.key_id

    # --- watermark (DWT carrier) ---
    carrier = pdf_builder.extract_carrier_image(pdf_path)
    if carrier is not None and claimed_root:
        watermark = verify_watermark_image(
            carrier, claimed_root, pdf_builder.watermark_key(baseline.document_id)
        )
    else:
        watermark = {
            "valid": False,
            "bit_error_rate": 1.0,
            "bits_checked": settings.DWT_BITS,
            "bits_matched": 0,
            "expected_prefix": claimed_root[:16],
            "recovered_prefix": "",
            "tolerance": 0.08,
            "note": "no DWT watermark carrier found in the document",
        }
    step(
        "Invisible watermark",
        watermark["valid"],
        f"DWT payload bit-error rate {watermark['bit_error_rate']:.3f} "
        f"({watermark['bits_matched']}/{watermark['bits_checked']} bits recovered)",
    )

    # --- signature ---
    signature_valid = verify_root_signature(db, claimed_root, claimed_signature, claimed_key_id)
    step(
        "Digital signature",
        signature_valid,
        f"{baseline.algorithm} signature over the Merkle root "
        f"{'validates against registered key ' + (claimed_key_id or '?') if signature_valid else 'does NOT validate'}",
    )

    # --- fragment recomputation ---
    recomputed, markers = fragment_pdf(pdf_path)
    step(
        "Fragment recomputation",
        True,
        f"{len(recomputed)} fragments re-hashed (SHA-256, "
        f"{settings.FRAGMENT_ROWS}x{settings.FRAGMENT_COLS} grid per page)",
    )

    comparison = compare_fragments(baseline, recomputed, markers)
    step(
        "Fragment comparison",
        comparison["modified"] == 0 and comparison["missing"] == 0 and comparison["added"] == 0,
        f"{comparison['intact']} intact · {comparison['modified']} modified · "
        f"{comparison['missing']} missing · {comparison['added']} added",
    )

    # --- Merkle rebuild ---
    ordered = {(f.page_index, f.cell_index): f.fragment_hash for f in recomputed}
    rebuilt_leaves = [ordered.get(key, "00" * 32) for key in baseline.order]
    rebuilt_root = MerkleTree(rebuilt_leaves).root if baseline.order else ""
    merkle_match = bool(claimed_root) and rebuilt_root == claimed_root
    step(
        "Merkle root rebuild",
        merkle_match,
        f"recomputed root {rebuilt_root[:24]}… "
        f"{'matches' if merkle_match else 'does not match'} the signed root {claimed_root[:24]}…",
    )

    # Inclusion proof for the first offending fragment, from the issued tree.
    proof_demo = _inclusion_proof_demo(baseline, comparison["analysis"], claimed_root)

    revoked = document is not None and document.status == DocumentStatus.revoked
    if revoked:
        step(
            "Revocation list",
            False,
            f"document was revoked: {document.revoked_reason or 'no reason recorded'}",
        )
    else:
        step("Revocation list", True, "document is not on the revocation list")

    tamper_score = _tamper_score(comparison, merkle_match, signature_valid, watermark["valid"])
    verdict = _verdict(
        document=document,
        revoked=revoked,
        signature_valid=signature_valid,
        merkle_match=merkle_match,
        comparison=comparison,
        watermark_valid=watermark["valid"],
    )
    step(
        "Verdict",
        verdict == VerificationResult.authentic.value,
        f"{verdict.upper()} · tamper score {tamper_score}/100",
    )

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

    return {
        "result": verdict,
        "tamper_score": tamper_score,
        "verified_at": _now_iso(),
        "duration_ms": elapsed_ms,
        "file": {"name": file_name, "sha256": file_hash, "page_count": page_count},
        "document": _document_summary(document, baseline),
        "qr": {
            "found": evidence["qr_found"],
            "payload": qr_payload.to_public_dict() if qr_payload else None,
            "raw_count": evidence["qr_raw_count"],
        },
        "manifest_present": manifest is not None,
        "baseline_source": baseline.source,
        "signature": {
            "valid": signature_valid,
            "algorithm": baseline.algorithm,
            "key_id": claimed_key_id,
            "signed_root": claimed_root,
            "signature_preview": (claimed_signature[:40] + "…") if claimed_signature else "",
        },
        "merkle": {
            "match": merkle_match,
            "signed_root": claimed_root,
            "recomputed_root": rebuilt_root,
            "leaf_count": len(baseline.order),
            "proof_demo": proof_demo,
        },
        "watermark": watermark,
        "fragments": {
            "total": comparison["total"],
            "intact": comparison["intact"],
            "modified": comparison["modified"],
            "missing": comparison["missing"],
            "added": comparison["added"],
            "marker_issues": comparison["marker_issues"],
            "analysis": comparison["analysis"],
        },
        "heatmap": heatmap_regions(comparison["analysis"]),
        "revoked": revoked,
        "revoked_reason": document.revoked_reason if document else None,
        "timeline": timeline,
    }


def _document_summary(document: Document | None, baseline: Baseline) -> dict:
    if document is not None:
        return {
            "id": document.id,
            "name": document.document_name,
            "status": document.status.value,
            "issuer": document.issuer,
            "subject": document.subject,
            "issued_at": document.created_at.isoformat() if document.created_at else None,
            "page_count": document.page_count,
            "fragment_count": document.fragment_count,
            "registered": True,
        }
    return {
        "id": baseline.document_id,
        "name": None,
        "status": "unregistered",
        "issuer": None,
        "subject": None,
        "issued_at": baseline.issued_at,
        "page_count": None,
        "fragment_count": len(baseline.order),
        "registered": False,
    }


def _inclusion_proof_demo(baseline: Baseline, analysis: list[dict], claimed_root: str) -> dict:
    if not baseline.order:
        return {}
    leaves = [baseline.fragments[key]["fragment_hash"] for key in baseline.order]
    tree = MerkleTree(leaves)
    target = next(
        (a for a in analysis if a["status"] in (STATUS_MODIFIED, STATUS_MISSING)), None
    )
    index = 0
    if target is not None and 0 <= target["fragment_index"] < len(leaves):
        index = target["fragment_index"]
    proof = tree.proof(index)
    return {
        "fragment_index": index,
        "leaf_hash": leaves[index],
        "path": proof,
        "issued_root": tree.root,
        "root_matches_signed_root": tree.root == claimed_root,
        "proof_valid": verify_proof(leaves[index], proof, tree.root),
        "is_tampered_fragment": target is not None,
    }


def _tamper_score(
    comparison: dict, merkle_match: bool, signature_valid: bool, watermark_valid: bool
) -> float:
    total = max(comparison["total"], 1)
    damaged = comparison["modified"] + comparison["missing"] + comparison["added"]
    fragment_component = min(damaged / total, 1.0)
    score = (
        settings.W_FRAGMENT * fragment_component
        + settings.W_MERKLE * (0.0 if merkle_match else 1.0)
        + settings.W_SIGNATURE * (0.0 if signature_valid else 1.0)
        + settings.W_WATERMARK * (0.0 if watermark_valid else 1.0)
    )
    return round(min(score, 1.0) * 100, 1)


def _verdict(
    *,
    document: Document | None,
    revoked: bool,
    signature_valid: bool,
    merkle_match: bool,
    comparison: dict,
    watermark_valid: bool,
) -> str:
    if revoked:
        return VerificationResult.revoked.value
    if not signature_valid:
        return VerificationResult.invalid.value
    damaged = comparison["modified"] + comparison["missing"] + comparison["added"]
    if damaged == 0 and merkle_match and watermark_valid:
        return (
            VerificationResult.authentic.value
            if document is not None
            else VerificationResult.unknown.value
        )
    return VerificationResult.tampered.value


def _unprotected_result(
    file_name: str,
    file_hash: str,
    page_count: int,
    timeline: list[dict],
    started: datetime,
    claimed_document_id: str | None,
) -> dict:
    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    return {
        "result": VerificationResult.unknown.value,
        "tamper_score": 100.0,
        "verified_at": _now_iso(),
        "duration_ms": elapsed_ms,
        "file": {"name": file_name, "sha256": file_hash, "page_count": page_count},
        "document": {
            "id": claimed_document_id,
            "name": None,
            "status": "unprotected",
            "issuer": None,
            "subject": None,
            "issued_at": None,
            "page_count": page_count,
            "fragment_count": 0,
            "registered": False,
        },
        "qr": {"found": False, "payload": None, "raw_count": 0},
        "manifest_present": False,
        "baseline_source": "none",
        "signature": {
            "valid": False,
            "algorithm": "n/a",
            "key_id": None,
            "signed_root": "",
            "signature_preview": "",
        },
        "merkle": {
            "match": False,
            "signed_root": "",
            "recomputed_root": "",
            "leaf_count": 0,
            "proof_demo": {},
        },
        "watermark": {
            "valid": False,
            "bit_error_rate": 1.0,
            "bits_checked": 0,
            "bits_matched": 0,
            "expected_prefix": "",
            "recovered_prefix": "",
            "tolerance": 0.08,
            "note": "document carries no watermark carrier",
        },
        "fragments": {
            "total": 0,
            "intact": 0,
            "modified": 0,
            "missing": 0,
            "added": 0,
            "marker_issues": 0,
            "analysis": [],
        },
        "heatmap": [],
        "revoked": False,
        "revoked_reason": None,
        "timeline": timeline
        + [
            {
                "step": "Verdict",
                "ok": False,
                "detail": "UNKNOWN · the file was never issued through this platform",
                "at": _now_iso(),
            }
        ],
    }
