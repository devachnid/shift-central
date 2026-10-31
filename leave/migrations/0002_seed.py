from datetime import date

from django.db import migrations

TYPES = [
    # name, draws_from, requestable, paid_choice, default_paid, on_payroll, colour
    ("Holiday", "annual", True, False, True, "leavers", "#2F6FB3"),
    ("Bank holiday", "bank_holiday", False, False, True, "never", "#5B7DB1"),
    ("TOIL", "toil", True, False, True, "never", "#4F8A6B"),
    ("Sick leave", "none", False, False, True, "always", "#C8553D"),
    ("Training", "none", True, False, True, "never", "#8E6BBF"),
    ("Maternity", "none", False, False, True, "always", "#D98FB3"),
    ("Paternity", "none", False, False, True, "always", "#D98FB3"),
    ("Adoption / shared parental", "none", False, False, True, "always", "#D98FB3"),
    ("KIT day", "none", False, False, True, "always", "#E0A458"),
    ("Dependants' leave", "none", False, True, True, "if_unpaid", "#B58B4C"),
    ("Compassionate", "none", True, True, True, "if_unpaid", "#7A7A7A"),
    ("Authorised absence", "none", True, True, True, "if_unpaid", "#6C8EAD"),
    ("Unpaid leave", "none", True, False, False, "always", "#9E9E9E"),
    ("Unauthorised absence", "none", False, False, True, "always", "#B00020"),
    ("Jury service", "none", False, False, True, "always", "#5C6B73"),
]

BANK_HOLIDAYS = {
    2026: [("01-01", "New Year's Day"), ("04-03", "Good Friday"), ("04-06", "Easter Monday"), ("05-04", "Early May bank holiday"),
           ("05-25", "Spring bank holiday"), ("08-31", "Summer bank holiday"), ("12-25", "Christmas Day"), ("12-28", "Boxing Day (substitute day)")],
    2027: [("01-01", "New Year's Day"), ("04-02", "Good Friday"), ("04-05", "Easter Monday"), ("05-03", "Early May bank holiday"),
           ("05-31", "Spring bank holiday"), ("08-30", "Summer bank holiday"), ("12-27", "Christmas Day (substitute day)"), ("12-28", "Boxing Day (substitute day)")],
}


def seed(apps, schema_editor):
    LeaveType = apps.get_model("leave", "LeaveType")
    BankHoliday = apps.get_model("leave", "BankHoliday")
    for order, (name, draws, req, choice, default_paid, payroll, colour) in enumerate(TYPES, start=10):
        LeaveType.objects.get_or_create(name=name, defaults={
            "draws_from": draws, "requestable": req, "paid_choice": choice, "default_paid": default_paid,
            "on_payroll": payroll, "colour": colour, "display_order": order * 10, "seeded": True})
    for year, days in BANK_HOLIDAYS.items():
        for md, name in days:
            BankHoliday.objects.get_or_create(day=date.fromisoformat(f"{year}-{md}"), defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("leave", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
