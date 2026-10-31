from django import template

from leave.services import hours

register = template.Library()


@register.filter
def hm(seconds):
    return hours.fmt(seconds or 0)


@register.filter
def get_item(mapping, key):
    return (mapping or {}).get(key)


@register.filter
def figure(value, field_name):
    """A correction's figure as the screen shows it: hours for hour fields,
    the number or date otherwise."""
    from payroll.services import report
    if value is None:
        return ""
    if field_name in report.HOUR_FIELDS or str(field_name).endswith(" hours") or field_name == "leaver_balance":
        return hours.fmt(value)
    if field_name == "leave_half_days":
        whole, half = divmod(int(value), 2)
        return f"{whole or ''}{'½' if half else ''}" or "0"
    return value


@register.filter
def year_label(value):
    from leave.services import years
    return years.label(value)
