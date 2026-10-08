"""Generates realistic demo PDFs (certificates, transcripts, letters) so the
platform can be demonstrated without hunting for sample files."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_certificate(
    path: Path,
    recipient: str = "Aarav Sharma",
    programme: str = "M.Tech. in Computer Science & Engineering",
    institution: str = "National Institute of Technology",
    reference: str = "NIT/CSE/2026/00471",
    grade: str = "First Class with Distinction",
    issued: str | None = None,
) -> Path:
    issued = issued or date.today().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    pdf.setStrokeColor(colors.HexColor("#1e3a8a"))
    pdf.setLineWidth(3)
    pdf.rect(28, 110, width - 56, height - 150)

    pdf.setFillColor(colors.HexColor("#1e3a8a"))
    pdf.setFont("Helvetica-Bold", 19)
    pdf.drawCentredString(width / 2, height - 90, institution.upper())
    pdf.setFont("Helvetica", 10.5)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawCentredString(width / 2, height - 108, "Office of the Controller of Examinations")

    pdf.setFont("Helvetica-Bold", 15)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawCentredString(width / 2, height - 152, "CERTIFICATE OF DEGREE COMPLETION")

    body = [
        f"This is to certify that {recipient}, bearing enrolment reference {reference},",
        f"has successfully completed all academic requirements prescribed for the degree of",
        f"{programme} in the academic session 2024-2026.",
        "",
        f"The candidate has been placed in the {grade} category by the Board of Examiners",
        "and is hereby awarded the degree with all rights and privileges pertaining thereto.",
    ]
    pdf.setFont("Helvetica", 11)
    pdf.setFillColor(colors.HexColor("#1f2937"))
    y = height - 200
    for line in body:
        pdf.drawString(70, y, line)
        y -= 19

    rows = [
        ("Candidate", recipient),
        ("Enrolment Reference", reference),
        ("Programme", programme),
        ("Classification", grade),
        ("Date of Issue", issued),
        ("Credits Earned", "84 / 84"),
        ("CGPA", "9.14 / 10.00"),
    ]
    y -= 18
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.drawString(70, y, "ACADEMIC RECORD SUMMARY")
    y -= 8
    pdf.setStrokeColor(colors.HexColor("#cbd5e1"))
    pdf.setLineWidth(0.8)
    pdf.line(70, y, width - 70, y)
    y -= 18
    for label, value in rows:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(colors.HexColor("#475569"))
        pdf.drawString(74, y, label)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColor(colors.HexColor("#0f172a"))
        pdf.drawString(260, y, value)
        y -= 17

    y -= 26
    pdf.setFont("Helvetica", 9.5)
    pdf.setFillColor(colors.HexColor("#475569"))
    pdf.drawString(70, y, "Registrar")
    pdf.drawString(width - 190, y, "Controller of Examinations")
    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.line(70, y + 30, 210, y + 30)
    pdf.line(width - 190, y + 30, width - 60, y + 30)

    pdf.showPage()
    pdf.save()
    return path


def build_transcript(path: Path, recipient: str = "Aarav Sharma") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    courses = [
        ("CS601", "Advanced Algorithms", "4", "A"),
        ("CS612", "Applied Cryptography", "4", "A+"),
        ("CS623", "Distributed Systems", "3", "A"),
        ("CS634", "Machine Learning", "4", "A"),
        ("CS645", "Information Security", "3", "A+"),
        ("CS656", "Digital Forensics", "3", "B+"),
        ("CS667", "Secure Software Design", "3", "A"),
        ("CS678", "Research Methodology", "2", "A"),
    ]
    pdf.setFont("Helvetica-Bold", 16)
    pdf.setFillColor(colors.HexColor("#1e3a8a"))
    pdf.drawString(60, height - 70, "OFFICIAL ACADEMIC TRANSCRIPT")
    pdf.setFont("Helvetica", 10.5)
    pdf.setFillColor(colors.HexColor("#334155"))
    pdf.drawString(60, height - 90, f"Candidate: {recipient}    Programme: M.Tech. CSE")

    y = height - 130
    pdf.setFont("Helvetica-Bold", 10)
    pdf.setFillColor(colors.HexColor("#0f172a"))
    for header, x in (("Code", 60), ("Course Title", 130), ("Credits", 360), ("Grade", 440)):
        pdf.drawString(x, y, header)
    y -= 6
    pdf.line(60, y, width - 60, y)
    y -= 18
    for code, title, credits, grade in courses:
        pdf.setFont("Helvetica", 10)
        pdf.setFillColor(colors.HexColor("#1f2937"))
        pdf.drawString(60, y, code)
        pdf.drawString(130, y, title)
        pdf.drawString(370, y, credits)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(445, y, grade)
        y -= 20

    y -= 10
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(60, y, "Cumulative Grade Point Average: 9.14 / 10.00")
    pdf.showPage()
    pdf.save()
    return path
