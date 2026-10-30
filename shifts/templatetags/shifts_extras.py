"""Three one-line filters the rota templates need: a dict lookup by a
runtime key, a comma split for a literal list, and a form field by name."""

from django import template

register = template.Library()


@register.filter
def get_item(d, key):
    return (d or {}).get(key, [])


@register.filter
def split(s, sep=","):
    return s.split(sep)


@register.filter
def field(form, name):
    return form[name]
