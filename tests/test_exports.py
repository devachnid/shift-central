"""The two writers every download shares: a workbook whose text cells are
text (a name beginning with = is a name), and a PDF with the logo."""

import io
from datetime import date

from openpyxl import load_workbook

from exports import pdf, xlsx


def test_the_workbook_types_text_as_text_and_hours_as_decimal_hours():
    content = xlsx.workbook([("Payroll", ["Name", "Worked", "Started"],
                              [["=cmd|' /C calc'!A0", xlsx.Hours(27000), date(2027, 1, 4)], ["Sam", xlsx.Hours(0), None]])])
    wb = load_workbook(io.BytesIO(content))
    ws = wb["Payroll"]
    assert ws["A1"].value == "Name" and ws["A1"].font.bold
    assert ws["A2"].value == "=cmd|' /C calc'!A0" and ws["A2"].data_type == "s"
    assert ws["B2"].value == 7.5 and ws["B2"].number_format == "0.00"
    assert ws["C2"].value.date() == date(2027, 1, 4) and ws["C3"].value is None
    r = xlsx.response(content, "payroll-2027-01.xlsx")
    assert r["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r["Content-Disposition"] == 'attachment; filename="payroll-2027-01.xlsx"'


def test_the_pdf_has_the_title_and_a_table():
    content = pdf.document("Sickness summary", "1 Jul 2026 to 31 Dec 2026", [("Practice", ["People", "Instances"], [["59", "12"]])], "Generated 2 Nov 2026 by Boss")
    assert content.startswith(b"%PDF") and b"/Title (Sickness summary)" in content and b"/Type /Page" in content and len(content) > 2000
    r = pdf.response(content, "sickness-2026-07-01-2026-12-31.pdf")
    assert r["Content-Type"] == "application/pdf" and 'filename="sickness-2026-07-01-2026-12-31.pdf"' in r["Content-Disposition"]


def test_markup_in_a_title_or_heading_is_text_not_markup():
    content = pdf.document("A & B <i>x</i>", "r <img src='/etc/hostname'/>", [("Team <b>", ["H"], [["v"]])], "f")
    assert content.startswith(b"%PDF")


def test_the_pdf_builds_without_the_logo(monkeypatch):
    monkeypatch.setattr(pdf.finders, "find", lambda path: None)
    content = pdf.document("No logo", "r", [("Team", ["H"], [["v"]])], "f")
    assert content.startswith(b"%PDF") and b"/Type /Page" in content


def test_control_characters_and_forbidden_sheet_title_characters_are_stripped():
    content = xlsx.workbook([("A/B", ["Note"], [["bell\x07 ring"]])])
    wb = load_workbook(io.BytesIO(content))
    assert wb.sheetnames == ["A B"]
    assert wb["A B"]["A2"].value == "bell ring"
