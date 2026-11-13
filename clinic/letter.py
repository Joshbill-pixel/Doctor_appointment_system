"""Printable appointment letter (A4 PDF) with an ID, a verification token and a QR code."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas

NAVY = HexColor("#0B4A82")
TEAL = HexColor("#0F9D8F")
GOLD = HexColor("#F2A900")
INK = HexColor("#0F172A")
MUTED = HexColor("#5B6B7F")
LINE = HexColor("#D8E2EE")
PANEL = HexColor("#F1F6FB")
RED = HexColor("#C8102E")

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=INK)


def _group(code, size=4):
    return "-".join(code[i:i + size] for i in range(0, len(code), size))


def _box(c, x, y, w, h, label, value, value_font="Courier-Bold", value_size=15):
    c.setFillColor(PANEL)
    c.setStrokeColor(LINE)
    c.roundRect(x, y, w, h, 3 * mm, stroke=1, fill=1)
    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(x + 5 * mm, y + h - 6.5 * mm, label.upper())
    c.setFillColor(NAVY)
    c.setFont(value_font, value_size)
    c.drawString(x + 5 * mm, y + 5 * mm, value)


def _paragraph(c, text, x, top, width, style=BODY):
    para = Paragraph(escape(text), style)
    _, height = para.wrapOn(c, width, 400 * mm)
    para.drawOn(c, x, top - height)
    return top - height


def _qr(c, value, x, y, size):
    widget = qr.QrCodeWidget(value, barBorder=2)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / width, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)


def build_appointment_letter(appt, verify_url):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Appointment letter {appt.display_id}")
    c.setAuthor(settings.CLINIC_NAME)
    c.setSubject("Medical appointment confirmation")
    w, h = A4
    margin = 18 * mm

    # Letterhead
    c.setFillColor(NAVY)
    c.rect(0, h - 40 * mm, w, 40 * mm, stroke=0, fill=1)
    c.setFillColor(GOLD)
    c.rect(0, h - 43 * mm, w, 3 * mm, stroke=0, fill=1)
    badge = finders.find("img/bsu-badge.png")
    if badge:
        c.drawImage(badge, margin, h - 37 * mm, width=21 * mm, height=23.4 * mm, mask="auto",
                    preserveAspectRatio=True)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(margin + 28 * mm, h - 16 * mm, settings.CLINIC_NAME.upper())
    c.setFont("Helvetica", 9.5)
    c.drawString(margin + 28 * mm, h - 23 * mm, settings.CLINIC_FULL_NAME)
    c.setFillColor(HexColor("#BFDBFE"))
    c.setFont("Helvetica", 8.5)
    c.drawString(margin + 28 * mm, h - 29 * mm, settings.CLINIC_ADDRESS)
    c.drawString(margin + 28 * mm, h - 34 * mm, f"Tel: {settings.CLINIC_PHONE}   ·   {settings.CLINIC_EMAIL}")

    # Title and codes
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 21)
    c.drawString(margin, h - 58 * mm, "Appointment Letter")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    issued = timezone.localdate().strftime("%d %B %Y")
    c.drawString(margin, h - 64 * mm, f"Issued {issued}  ·  Keep this letter and bring it on the day of your visit.")

    box_top = h - 70 * mm
    _box(c, margin, box_top - 22 * mm, 72 * mm, 22 * mm, "Appointment ID", appt.display_id)
    _box(c, margin + 78 * mm, box_top - 22 * mm, 96 * mm, 22 * mm, "Verification token", _group(appt.token), value_size=12.5)

    # Details
    day_label = appt.date.strftime("%A, %d %B %Y")
    start = appt.start_time.strftime("%I:%M %p").lstrip("0")
    end = appt.end_time.strftime("%I:%M %p").lstrip("0")
    rows = [
        ("Patient", appt.patient_name),
        ("Doctor", appt.doctor.display_name),
        ("Department", appt.department.title),
        ("Date", day_label),
        ("Time", f"{start} – {end}"),
        ("Venue", settings.CLINIC_ADDRESS),
        ("Status", appt.get_status_display()),
    ]
    y = box_top - 30 * mm
    for label, value in rows:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9)
        c.drawString(margin, y, label)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(margin + 36 * mm, y, value[:90])
        y -= 2.5 * mm
        c.setStrokeColor(LINE)
        c.setLineWidth(0.5)
        c.line(margin, y, w - margin, y)
        y -= 6.5 * mm

    # Instructions and QR code
    y -= 4 * mm
    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Before your visit")
    y -= 6 * mm
    tips = [
        "Arrive 15 minutes before your appointment time and report to the reception desk.",
        "Bring this letter (printed or on your phone) and a valid means of identification.",
        "Bring any previous prescriptions, test results or referral notes.",
        f"Need to change plans? Reschedule or cancel in the portal at least {settings.CHANGE_CUTOFF_HOURS} hours before the visit.",
    ]
    for tip in tips:
        y = _paragraph(c, "•  " + tip, margin, y, 118 * mm, BODY) - 2.2 * mm

    qr_size = 40 * mm
    qr_x = w - margin - qr_size
    qr_y = h - 218 * mm
    c.setFillColor(white)
    c.setStrokeColor(LINE)
    c.roundRect(qr_x - 3 * mm, qr_y - 14 * mm, qr_size + 6 * mm, qr_size + 20 * mm, 3 * mm, stroke=1, fill=1)
    _qr(c, verify_url, qr_x, qr_y, qr_size)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 7 * mm, "Scan to verify")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 11 * mm, f"Or enter ID or token at /verify")

    # Signature
    sig_y = h - 236 * mm
    c.setStrokeColor(INK)
    c.line(margin, sig_y, margin + 62 * mm, sig_y)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, sig_y - 4.5 * mm, "Authorised by the Medical Records Office")
    c.drawString(margin, sig_y - 9 * mm, settings.CLINIC_NAME)

    # Footer
    c.setStrokeColor(LINE)
    c.line(margin, 24 * mm, w - margin, 24 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(margin, 19 * mm, "This letter is valid only while the appointment is scheduled. "
                                  "Contains confidential health-service information.")
    c.drawString(margin, 15 * mm, f"Verify online: {settings.SITE_URL}/verify/  ·  Appointment ID {appt.display_id}")

    if appt.status == appt.Status.CANCELLED:
        c.saveState()
        c.translate(w / 2, h / 2)
        c.rotate(35)
        c.setFillColor(Color(0.78, 0.06, 0.18, alpha=0.12))
        c.setFont("Helvetica-Bold", 96)
        c.drawCentredString(0, 0, "CANCELLED")
        c.restoreState()

    c.showPage()
    c.save()
    return buffer.getvalue()
