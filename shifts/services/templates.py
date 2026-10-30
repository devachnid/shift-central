"""Saved blocks (spec, section 5). Audited on shifts.template; the block
itself is not put in the log (it can be large), only the name."""

from django.db import IntegrityError, transaction

from people.services import audit
from shifts.models import Template


def save(user, name, block):
    if not isinstance(block, dict) or not isinstance(block.get("rows"), list):
        raise ValueError("the block has no rows")
    try:
        with transaction.atomic():
            t = Template.objects.create(name=name.strip(), created_by=user, block=block)
    except IntegrityError:
        raise ValueError("A template with this name already exists.") from None
    audit.record(user, t, {"name": ("", t.name)}, note="template saved")
    return t


def rename(user, template, name):
    before = template.name
    template.name = name.strip()
    try:
        with transaction.atomic():
            template.save(update_fields=["name"])
    except IntegrityError:
        raise ValueError("A template with this name already exists.") from None
    audit.record(user, template, {"name": (before, template.name)}, note="template renamed")
    return template


def delete(user, template):
    audit.record(user, template, {"name": (template.name, "")}, note="template deleted")
    template.delete()
