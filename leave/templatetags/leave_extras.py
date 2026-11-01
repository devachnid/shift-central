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
def year_label(value):
    from leave.services import years
    return years.label(value)
