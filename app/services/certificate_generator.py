"""PDF generation with ReportLab (one fixed, built-in certificate design).

This module knows nothing about FastAPI or the database, which makes it easy
to test and to replace.
"""
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

NAVY = colors.HexColor("#1f3a5f")
GOLD = colors.HexColor("#b8902f")
GREY = colors.HexColor("#555555")

PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)
CONTENT_WIDTH = PAGE_WIDTH - 200


# ReportLab's built-in fonts (no external font files needed) use WinAnsi
# encoding, i.e. Latin characters only.
SUPPORTED_ENCODING = "cp1252"


class UnsupportedCharactersError(ValueError):
    """Text contains characters the built-in certificate fonts cannot draw."""


@dataclass(frozen=True)
class CertificateData:
    certificate_code: str
    recipient_name: str
    event_name: str
    event_date: date
    organization_name: str


def generate_certificate_pdf(data: CertificateData, output_path: Path) -> None:
    """Write the certificate PDF to output_path.

    The PDF is written to a temporary file and renamed, so a failed run never
    leaves a half-written certificate behind.
    """
    _ensure_text_is_supported(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    try:
        _draw_certificate(data, temp_path)
        temp_path.replace(output_path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _ensure_text_is_supported(data: CertificateData) -> None:
    """Fail clearly instead of silently drawing black boxes for unknown glyphs."""
    fields = {
        "recipient name": data.recipient_name,
        "event name": data.event_name,
        "organization name": data.organization_name,
    }
    for label, text in fields.items():
        try:
            text.encode(SUPPORTED_ENCODING)
        except UnicodeEncodeError as exc:
            bad = text[exc.start : exc.end]
            raise UnsupportedCharactersError(
                f"The {label} contains characters the built-in certificate font "
                f"cannot render (e.g. {bad!r}). Only Latin characters are supported."
            ) from exc


def _draw_certificate(data: CertificateData, path: Path) -> None:
    pdf = Canvas(str(path), pagesize=landscape(A4))
    pdf.setTitle(f"Certificate {data.certificate_code}")
    pdf.setAuthor(data.organization_name)

    _draw_border(pdf)
    center_x = PAGE_WIDTH / 2

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 34)
    pdf.drawCentredString(center_x, PAGE_HEIGHT - 135, "CERTIFICATE OF PARTICIPATION")
    _draw_divider(pdf, PAGE_HEIGHT - 153, 160)

    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica-Oblique", 16)
    pdf.drawCentredString(center_x, PAGE_HEIGHT - 195, "This certificate is proudly presented to")

    name_size = _fit_font_size(data.recipient_name, "Times-BoldItalic", 44, CONTENT_WIDTH)
    pdf.setFillColor(GOLD)
    pdf.setFont("Times-BoldItalic", name_size)
    pdf.drawCentredString(center_x, PAGE_HEIGHT - 250, data.recipient_name)
    _draw_divider(pdf, PAGE_HEIGHT - 265, 220)

    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica-Oblique", 16)
    pdf.drawCentredString(center_x, PAGE_HEIGHT - 300, "for successfully participating in")

    y = PAGE_HEIGHT - 337
    y = _draw_wrapped(pdf, data.event_name, "Helvetica-Bold", 24, NAVY, y, leading=30)
    y = _draw_wrapped(
        pdf, f"conducted by {data.organization_name}", "Helvetica", 16, GREY, y - 4, leading=22
    )

    _draw_footer(pdf, data)
    pdf.showPage()
    pdf.save()


def _draw_border(pdf: Canvas) -> None:
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(6)
    pdf.rect(25, 25, PAGE_WIDTH - 50, PAGE_HEIGHT - 50)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)
    pdf.rect(38, 38, PAGE_WIDTH - 76, PAGE_HEIGHT - 76)

    # Small gold squares in the corners.
    pdf.setFillColor(GOLD)
    for x in (38, PAGE_WIDTH - 38):
        for y in (38, PAGE_HEIGHT - 38):
            pdf.rect(x - 6, y - 6, 12, 12, stroke=0, fill=1)


def _draw_divider(pdf: Canvas, y: float, half_width: float) -> None:
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)
    center_x = PAGE_WIDTH / 2
    pdf.line(center_x - half_width, y, center_x + half_width, y)


def _draw_footer(pdf: Canvas, data: CertificateData) -> None:
    base_y = 95
    left_x, right_x, center_x = 90, PAGE_WIDTH - 90, PAGE_WIDTH / 2

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica", 12)
    pdf.drawString(left_x, base_y, f"Date: {data.event_date.strftime('%d %B %Y')}")
    pdf.drawRightString(right_x, base_y, f"Certificate ID: {data.certificate_code}")

    # Signature line + authorised-by text.
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(0.8)
    pdf.line(center_x - 90, base_y + 8, center_x + 90, base_y + 8)
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(GREY)
    pdf.drawCentredString(center_x, base_y - 6, "Authorized Signatory")


def _draw_wrapped(
    pdf: Canvas,
    text: str,
    font: str,
    size: int,
    color: colors.Color,
    y: float,
    leading: int,
) -> float:
    """Draw centred text, wrapping long lines. Returns the next free y."""
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    for line in simpleSplit(text, font, size, CONTENT_WIDTH):
        pdf.drawCentredString(PAGE_WIDTH / 2, y, line)
        y -= leading
    return y


def _fit_font_size(text: str, font: str, max_size: int, max_width: float, min_size: int = 12) -> int:
    """Shrink the font until the text fits on one line."""
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 1
    return size
