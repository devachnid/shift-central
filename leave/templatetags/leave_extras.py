from django import template

from leave.services import hours

register = template.Library()


@register.filter
def hm(seconds):
    return hours.fmt(seconds or 0)
