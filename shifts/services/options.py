"""The Options panel's ticks (spec, section 2): defaults, the merge with
what the user saved, and the save that drops anything not an option."""

from shifts.models import GridOptions

DEFAULTS = {
    "staff_colours": True, "job_titles": False, "department_colours": True, "float_headers": True,
    "my_shifts_on_top": False, "only_my_shifts": False, "hide_no_shifts": False,
    "font_size": "md", "spacing": "normal", "days": [0, 1, 2, 3, 4, 5, 6], "paste": "replace",
}
CHOICES = {"font_size": ("sm", "md", "lg"), "spacing": ("tight", "normal", "loose"), "paste": ("replace", "add")}


def for_user(user):
    saved = GridOptions.objects.filter(user=user).values_list("data", flat=True).first() or {}
    return {**DEFAULTS, **{k: v for k, v in saved.items() if k in DEFAULTS}}


def clean(data):
    out = {}
    for key, default in DEFAULTS.items():
        if key not in data:
            continue
        value = data[key]
        if key in CHOICES:
            out[key] = value if value in CHOICES[key] else default
        elif key == "days":
            out[key] = sorted({int(d) for d in value if str(d).isdigit() and 0 <= int(d) <= 6}) or default
        else:
            out[key] = bool(value)
    return out


def save(user, data):
    row, _ = GridOptions.objects.get_or_create(user=user)
    row.data = {**row.data, **clean(data)}
    row.save(update_fields=["data"])
    return for_user(user)
