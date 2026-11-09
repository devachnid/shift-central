"""The Person and Team boxes on the reports. A choice only ever narrows what
the viewer may already see: an id outside the choices is no filter at all."""

from urllib.parse import urlencode


def chosen(request, choices, key):
    """The row among `choices` (a queryset or a list) whose id the GET
    parameter `key` names, else None."""
    value = request.GET.get(key, "")
    if not (value.isascii() and value.isdigit()):
        return None
    pk = int(value)
    return next((row for row in choices if row.pk == pk), None)


def query(**rows):
    """`&person=3` and the like, for the links that must keep the filter
    (downloads, the previous and next period); empty when nothing is chosen."""
    picked = {key: row.pk for key, row in rows.items() if row is not None}
    return "&" + urlencode(picked) if picked else ""
