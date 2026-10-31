"""One-page summaries as PDF (REP-04, REP-05): A4 landscape, the logo, a
title and range, one table per section with its header repeated on each
page, page numbers. Every cell is text."""

import io

from django.contrib.staticfiles import finders
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LOGO = "img/logo-dark.png"
NAVY = colors.HexColor("#143D5C")


def _logo():
    path = finders.find(LOGO)
    if not path:
        return None
    img = Image(path)
    ratio = img.imageWidth / img.imageHeight
    img.drawHeight, img.drawWidth = 10 * mm, 10 * mm * ratio
    img.hAlign = "LEFT"
    return img


def _table(header, rows):
    data = [[str(h) for h in header]] + [["" if v is None else str(v) for v in row] for row in rows]
    t = Table(data, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7C3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def document(title, subtitle, sections, footer):
    """sections: [(heading, header_row, rows)] -> the PDF bytes."""
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("h", parent=styles["Heading2"], textColor=NAVY, spaceBefore=6, spaceAfter=3)
    out = io.BytesIO()

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 8 * mm, footer)
        canvas.drawRightString(doc.pagesize[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=title, author="AMG Shift Central",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=15 * mm)
    story = []
    logo = _logo()
    if logo is not None:
        story += [logo, Spacer(1, 3 * mm)]
    story += [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Normal"]), Spacer(1, 4 * mm)]
    for name, header, rows in sections:
        story += [Paragraph(name, heading), _table(header, rows), Spacer(1, 4 * mm)]
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return out.getvalue()


def response(content, filename):
    r = HttpResponse(content, content_type="application/pdf")
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    return r
