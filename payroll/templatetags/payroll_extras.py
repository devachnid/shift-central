from django import template

from leave.services import hours
from payroll.services import report

register = template.Library()


@register.filter
def figure(value, field_name):
    """A correction's figure as the screen shows it: hours for hour fields,
    leave days in halves (a negative difference too: −½, −1½), the number or
    date otherwise."""
    if value is None:
        return ""
    if field_name in report.HOUR_FIELDS or str(field_name).endswith(" hours") or field_name == "leaver_balance":
        return hours.fmt(value)
    if field_name == "leave_half_days":
        return report.half_days_text(value)
    return value
