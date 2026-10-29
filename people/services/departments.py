from people.models import Department
from people.services import audit

FIELDS = ("name", "colour", "display_order", "archived")


def create(actor, name, colour, display_order=100):
    d = Department.objects.create(name=name, colour=colour, display_order=display_order)
    audit.record(actor, d, {"created": ("", name)})
    return d


def update(actor, department, **fields):
    changes = {}
    for name, after in fields.items():
        if name not in FIELDS:
            raise ValueError(f"not a department field: {name}")
        before = getattr(department, name)
        if before != after:
            changes[name] = (before, after)
            setattr(department, name, after)
    if changes:
        department.save(update_fields=list(changes))
    return audit.record(actor, department, changes)
