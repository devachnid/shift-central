"""ROTA-02's initial list, each with a distinct default colour managers
can change on the Departments page."""

from django.db import migrations

DEPARTMENTS = [
    ("Reception AG", "#2F6FB3"), ("Reception PMC", "#5B8FD6"), ("Cleaning PMC", "#8C7B6B"),
    ("Prescriptions", "#D98E2C"), ("Private Income", "#B6568A"), ("Workflow", "#5E9E5E"),
    ("VAS/Enhanced", "#C94C4C"), ("Scanning", "#8A8A3A"), ("Pharmacy", "#3A8A8A"),
    ("Secretarial", "#7A5EB3"), ("Management", "#143D5C"), ("Salaried GP", "#2A7F62"),
    ("Nursing", "#D96C8A"), ("HCA", "#E0A030"), ("Phlebotomist", "#9A4C8A"),
    ("Pharmacist", "#3A6E8A"), ("Pharmacy Technician", "#6AA2C2"),
]


def seed(apps, schema_editor):
    Department = apps.get_model("people", "Department")
    for order, (name, colour) in enumerate(DEPARTMENTS, start=10):
        Department.objects.get_or_create(name=name, defaults={"colour": colour,
                                                              "display_order": order})


class Migration(migrations.Migration):
    dependencies = [("people", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
