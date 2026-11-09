"""The payroll Excel (PAY-03): three sheets from the report's rows. Hours
are decimal hours; names and notes are text cells."""

from django.utils import timezone

from exports import xlsx
from payroll.services import report

FIXED = ["Name", "Team", "Worked", "Paid leave", "Total to pay", "Paid overtime", "Unpaid leave", "Sickness", "Sickness instances", "TOIL taken", "Leave days"]


def _hours_field(field_name):
    return field_name in report.HOUR_FIELDS or field_name.endswith(" hours") or field_name == "leaver_balance"


def _cell(value, field_name):
    """A correction's figure: hours as decimal hours, else as it is."""
    if value is None:
        return None
    if field_name == "leave_half_days":
        return value / 2
    return xlsx.Hours(value) if _hours_field(field_name) else value


def _row(r, names):
    out = [r.person.name, r.team, xlsx.Hours(r.worked), xlsx.Hours(r.paid_leave), xlsx.Hours(r.total), xlsx.Hours(r.paid_overtime),
           xlsx.Hours(r.unpaid), xlsx.Hours(r.sickness), r.sickness_instances, xlsx.Hours(r.toil_taken), r.leave_half_days / 2]
    for name in names:
        slot = r.types.get(name, {"days": 0, "seconds": 0})
        out += [slot["days"], xlsx.Hours(slot["seconds"])]
    out += [r.started, r.leaves, None if r.leaver_balance is None else xlsx.Hours(r.leaver_balance)]
    return out


def build(month, rows, names, corrections, run, only=None):
    """`only`: the person the page was filtered to, named in the title so a
    one-person sheet is never mistaken for the month's."""
    header = FIXED + [h for name in names for h in (f"{name} (days)", f"{name} (hours)")] + ["Started", "Leaves", "Leaver's leave remaining"]
    status = f"Sent {timezone.localtime(run.sent_at):%-d %b %Y}" if run else "Draft"
    title = f"{month:%B %Y} — {status}" + (f" — {only.name} only" if only is not None else "")
    payroll = [[title] + [None] * (len(header) - 1)] + [_row(r, names) for r in rows]
    corr = [[c.month.strftime("%B %Y"), c.person.name, c.label, _cell(c.sent, c.field), _cell(c.now, c.field), _cell(c.delta, c.field)] for c in corrections]
    movers = [[r.person.name, r.team, r.started, r.leaves, None if r.leaver_balance is None else xlsx.Hours(r.leaver_balance)]
              for r in rows if r.started or r.leaves]
    return xlsx.workbook([("Payroll", header, payroll), ("Corrections", ["Month", "Name", "Figure", "Sent", "Now", "Difference"], corr),
                          ("Starters and leavers", ["Name", "Team", "Started", "Leaves", "Leave remaining (negative = over)"], movers)])
