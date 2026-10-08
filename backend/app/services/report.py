"""Verification report rendering (PDF) plus optional e-mail delivery."""
from __future__ import annotations

import io
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

VERDICT_COLORS = {
    "authentic": colors.HexColor("#047857"),
    "tampered": colors.HexColor("#b91c1c"),
    "revoked": colors.HexColor("#b45309"),
    "invalid": colors.HexColor("#b91c1c"),
    "unknown": colors.HexColor("#475569"),
}


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontSize=17, textColor=colors.HexColor("#0f172a")
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontSize=11.5,
            spaceBefore=12,
            textColor=colors.HexColor("#1e3a8a"),
        ),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9, leading=13),
        "mono": ParagraphStyle(
            "mono", parent=base["BodyText"], fontName="Courier", fontSize=7.4, leading=10
        ),
    }


def _table(rows: list[list[str]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]
        )
    )
    return table


def build_verification_report(result: dict, log_id: str, path: Path | None = None) -> bytes:
    """Render a verification result as a printable PDF report."""
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Verification Report {log_id}",
        author="QR-Linked Fragmented Watermarking Platform",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    verdict = str(result.get("result", "unknown"))
    colour = VERDICT_COLORS.get(verdict, colors.HexColor("#475569"))
    document = result.get("document", {}) or {}
    signature = result.get("signature", {}) or {}
    merkle = result.get("merkle", {}) or {}
    watermark = result.get("watermark", {}) or {}
    fragments = result.get("fragments", {}) or {}

    story = [
        Paragraph("Document Authentication Report", styles["h1"]),
        Paragraph(
            "QR-Linked Fragmented Watermarking · Merkle-tree integrity · RSA-PSS signature",
            styles["body"],
        ),
        Spacer(1, 7),
        HRFlowable(width="100%", color=colors.HexColor("#cbd5e1"), thickness=0.8),
        Spacer(1, 10),
        Paragraph(
            f'<font size="15" color="{colour.hexval()}"><b>VERDICT: {verdict.upper()}</b></font>'
            f'&nbsp;&nbsp;<font size="9" color="#475569">tamper score '
            f'{result.get("tamper_score", 0)}/100</font>',
            styles["body"],
        ),
        Spacer(1, 12),
        Paragraph("Report metadata", styles["h2"]),
        _table(
            [
                ["Field", "Value"],
                ["Report ID", log_id],
                ["Verified at", str(result.get("verified_at", ""))],
                ["Processing time", f"{result.get('duration_ms', 0)} ms"],
                ["File name", str((result.get("file") or {}).get("name", ""))],
                ["File SHA-256", str((result.get("file") or {}).get("sha256", ""))],
                ["Pages", str((result.get("file") or {}).get("page_count", ""))],
                ["Baseline source", str(result.get("baseline_source", ""))],
            ],
            [38 * mm, 136 * mm],
        ),
        Paragraph("Document identity", styles["h2"]),
        _table(
            [
                ["Field", "Value"],
                ["Document ID", str(document.get("id") or "—")],
                ["Document name", str(document.get("name") or "—")],
                ["Registered with issuer", "yes" if document.get("registered") else "no"],
                ["Status", str(document.get("status") or "—")],
                ["Issuer", str(document.get("issuer") or "—")],
                ["Subject", str(document.get("subject") or "—")],
                ["Issued at", str(document.get("issued_at") or "—")],
            ],
            [38 * mm, 136 * mm],
        ),
        Paragraph("Cryptographic checks", styles["h2"]),
        _table(
            [
                ["Check", "Outcome", "Detail"],
                [
                    "QR payload",
                    "found" if (result.get("qr") or {}).get("found") else "not found",
                    "payload decoded from the footer stamp",
                ],
                [
                    "Digital signature",
                    "valid" if signature.get("valid") else "INVALID",
                    f"{signature.get('algorithm', '')} · key {signature.get('key_id') or '—'}",
                ],
                [
                    "Merkle root",
                    "match" if merkle.get("match") else "MISMATCH",
                    f"{merkle.get('leaf_count', 0)} leaves",
                ],
                [
                    "DWT watermark",
                    "valid" if watermark.get("valid") else "INVALID",
                    f"BER {watermark.get('bit_error_rate', 1.0)} · "
                    f"{watermark.get('bits_matched', 0)}/{watermark.get('bits_checked', 0)} bits",
                ],
                [
                    "Revocation",
                    "revoked" if result.get("revoked") else "not revoked",
                    str(result.get("revoked_reason") or "—"),
                ],
            ],
            [34 * mm, 26 * mm, 114 * mm],
        ),
        Spacer(1, 6),
        Paragraph("Signed Merkle root", styles["h2"]),
        Paragraph(str(merkle.get("signed_root") or "—"), styles["mono"]),
        Paragraph("Recomputed Merkle root", styles["h2"]),
        Paragraph(str(merkle.get("recomputed_root") or "—"), styles["mono"]),
        Paragraph("Fragment analysis", styles["h2"]),
        _table(
            [
                ["Total", "Intact", "Modified", "Missing", "Added", "Marker issues"],
                [
                    str(fragments.get("total", 0)),
                    str(fragments.get("intact", 0)),
                    str(fragments.get("modified", 0)),
                    str(fragments.get("missing", 0)),
                    str(fragments.get("added", 0)),
                    str(fragments.get("marker_issues", 0)),
                ],
            ],
            [26 * mm, 26 * mm, 30 * mm, 28 * mm, 26 * mm, 38 * mm],
        ),
        Spacer(1, 8),
    ]

    damaged = [
        f
        for f in fragments.get("analysis", [])
        if f.get("status") != "intact"
    ]
    if damaged:
        story.append(Paragraph("Affected regions", styles["h2"]))
        rows = [["Page", "Cell", "Status", "Reason", "Marker"]]
        for item in damaged[:40]:
            rows.append(
                [
                    str(int(item.get("page_index", 0)) + 1),
                    str(item.get("cell_index", "")),
                    str(item.get("status", "")),
                    Paragraph(str(item.get("reason", "")), styles["body"]),
                    str(item.get("marker_status", "")),
                ]
            )
        story.append(_table(rows, [14 * mm, 14 * mm, 22 * mm, 100 * mm, 24 * mm]))
    else:
        story.append(
            Paragraph(
                "Every fragment reproduced its issued hash. No tampering detected.",
                styles["body"],
            )
        )

    story.append(Paragraph("Verification timeline", styles["h2"]))
    timeline_rows = [["Step", "Result", "Detail"]]
    for step in result.get("timeline", []):
        flag = {True: "pass", False: "fail", None: "info"}.get(step.get("ok"), "info")
        timeline_rows.append(
            [
                str(step.get("step", "")),
                flag,
                Paragraph(str(step.get("detail", "")), styles["body"]),
            ]
        )
    story.append(_table(timeline_rows, [40 * mm, 18 * mm, 116 * mm]))

    doc.build(story)
    data = buffer.getvalue()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return data


async def email_report(
    to_address: str, subject: str, body: str, attachment: bytes, filename: str
) -> dict:
    """Send a report by e-mail. Returns a dict describing what happened; SMTP
    settings are optional so the platform stays runnable without a mail server."""
    from email.message import EmailMessage

    from app.core.config import settings

    if not settings.SMTP_HOST:
        return {
            "sent": False,
            "reason": "SMTP is not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD)",
        }

    import aiosmtplib

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        attachment, maintype="application", subtype="pdf", filename=filename
    )

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_TLS,
        )
    except Exception as exc:  # pragma: no cover - depends on mail server
        return {"sent": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"sent": True, "reason": None}
