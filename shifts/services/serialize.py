"""Entries and changes as the island reads them."""

from shifts.services import render


def time(t):
    return t.strftime("%H:%M") if t else None


def entry(e):
    dept = e.department
    return {
        "id": e.pk, "kind": e.kind, "start": time(e.start), "finish": time(e.finish),
        "break_minutes": e.break_minutes, "department": dept.pk if dept else None,
        "department_name": dept.name if dept else "", "department_colour": dept.colour if dept else None,
        "text": e.text, "overtime": e.overtime, "wfh": e.wfh, "appearance": e.appearance,
        "hours": int(e.hours.total_seconds() // 60), "line": render.line(e),
    }


def changed(result):
    return {"cells": {str(pk): {day.isoformat(): [entry(e) for e in rows] for day, rows in days.items()}
                      for pk, days in result.cells.items()},
            "skipped": result.skipped}
