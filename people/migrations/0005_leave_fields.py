import datetime

from django.db import migrations, models


def fill_from_day(apps, schema_editor):
    Allowance = apps.get_model("people", "Allowance")
    for row in Allowance.objects.all():
        row.from_day = row.leave_year
        row.save(update_fields=["from_day"])


class Migration(migrations.Migration):

    dependencies = [
        ("people", "0004_syncrun_detail"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="allowance",
            options={"ordering": ["leave_year", "from_day"]},
        ),
        migrations.AddField(
            model_name="allowance",
            name="days_per_week",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="allowance",
            name="weekly_hours",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="allowance",
            name="from_day",
            field=models.DateField(default=datetime.date(2000, 1, 1), editable=False),
            preserve_default=False,
        ),
        migrations.RunPython(fill_from_day, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="allowance",
            name="one_allowance_per_person_per_year",
        ),
        migrations.AddConstraint(
            model_name="allowance",
            constraint=models.UniqueConstraint(
                fields=("person", "leave_year", "from_day"),
                name="one_allowance_per_person_year_and_day",
            ),
        ),
        migrations.AddField(
            model_name="person",
            name="leave_year_start",
            field=models.CharField(default="01-01", max_length=5),
        ),
        migrations.AddField(
            model_name="person",
            name="own_leave_without_approval",
            field=models.BooleanField(default=False),
        ),
    ]
