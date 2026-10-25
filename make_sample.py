"""Generate a synthetic one-page certificate to exercise the pipeline."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1000, 1280


def font(size: int):
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def main() -> None:
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 30], outline=0, width=3)
    d.text((70, 80), "NORTHGATE UNIVERSITY", font=font(34), fill=0)
    d.text((70, 130), "Office of the Registrar", font=font(20), fill=60)
    d.line([70, 175, W - 70, 175], fill=0, width=2)

    d.text((70, 215), "STATEMENT OF ACADEMIC RECORD", font=font(26), fill=0)

    rows = [
        ("Student", "Ritik Rana"),
        ("Enrolment no.", "NGU-2022-04417"),
        ("Programme", "B.Tech, Computer Science and Engineering"),
        ("Awarded", "First Class with Distinction"),
        ("CGPA", "9.14 / 10.00"),
        ("Credits earned", "168"),
        ("Date of issue", "01 October 2026"),
    ]
    y = 290
    for label, value in rows:
        d.text((90, y), f"{label}", font=font(19), fill=90)
        d.text((330, y), value, font=font(21), fill=0)
        y += 52

    d.line([70, y + 20, W - 70, y + 20], fill=120, width=1)
    y += 60
    body = (
        "This statement certifies the academic record held for the named\n"
        "student. The document is protected by QR-linked fragmented\n"
        "watermarking: every 32x32 pixel region carries an authenticator for\n"
        "a different region, and the QR code below anchors the whole page to\n"
        "a signed cryptographic commitment. Any alteration to the text,\n"
        "figures or seal will be detected and located."
    )
    d.multiline_text((90, y), body, font=font(18), fill=40, spacing=10)

    d.ellipse([W - 260, H - 320, W - 90, H - 150], outline=0, width=3)
    d.text((W - 232, H - 250), "REGISTRAR", font=font(16), fill=0)
    d.text((90, H - 170), "Signed:", font=font(18), fill=90)
    d.line([170, H - 150, 430, H - 150], fill=0, width=2)

    out = Path("samples/certificate.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote {out} ({W}x{H})")


if __name__ == "__main__":
    main()
