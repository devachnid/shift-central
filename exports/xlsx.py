"""Workbooks for the downloads (the payroll report and the two one-pagers).
Every text cell is typed as a string explicitly: openpyxl would otherwise
store a value beginning with = as a formula, and a name or a note typed in
the app can begin with one. Hours are written as decimal hours to two
places, which is what the bureau adds up."""

import io
import re
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Hours(int):
    """Seconds that a sheet shows as decimal hours."""

    @property
    def decimal(self):
        return round(int(self) / 3600, 2)


def _put(cell, value):
    if isinstance(value, Hours):
        cell.value, cell.number_format = value.decimal, "0.00"
    elif isinstance(value, bool):
        cell.value, cell.data_type = "Yes" if value else "No", "s"
    elif isinstance(value, (int, float, Decimal)):
        cell.value = value
    elif isinstance(value, (date, datetime)):
        cell.value, cell.number_format = value, "DD/MM/YYYY"
    elif value is None:
        cell.value = None
    else:
        cell.value, cell.data_type = ILLEGAL_CHARACTERS_RE.sub("", str(value)), "s"


def workbook(sheets):
    """sheets: [(title, header_row, rows)] -> the .xlsx bytes."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, header, rows in sheets:
        ws = wb.create_sheet(title=re.sub(r"[\\/?*\[\]:]", " ", title)[:31])
        for col, text in enumerate(header, start=1):
            c = ws.cell(row=1, column=col)
            _put(c, text)
            c.font = Font(bold=True)
        for r, row in enumerate(rows, start=2):
            for col, value in enumerate(row, start=1):
                _put(ws.cell(row=r, column=col), value)
        ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def response(content, filename):
    r = HttpResponse(content, content_type=XLSX)
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    return r
