from django import forms
from django.core.validators import RegexValidator

from people.models import HEX_COLOUR


class DisplayForm(forms.Form):
    job_title = forms.CharField(max_length=80, required=False)
    name_colour = forms.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR, "Choose a colour.")])
    display_order = forms.IntegerField(min_value=0, initial=100)
    display_on_rota = forms.BooleanField(required=False)
    show_to_other_staff = forms.BooleanField(required=False)
    can_see_other_staff = forms.BooleanField(required=False)


class HoursForm(forms.Form):
    """Weekly hours and days per week, plus the two allowances for each of
    the two leave years. The year fields are added in __init__ from
    profiles.leave_years(); the note is required only when the view finds
    an existing allowance changed (the service enforces it)."""
    weekly_hours = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, required=False)
    days_per_week = forms.IntegerField(min_value=1, max_value=7, required=False)
    note = forms.CharField(max_length=300, required=False, label="Reason for the change")

    def __init__(self, *args, years, is_gp=False, **kwargs):
        super().__init__(*args, **kwargs)
        if is_gp:
            del self.fields["weekly_hours"], self.fields["days_per_week"]
        self.years = years
        for year in years:
            self.fields[f"annual_{year.year}"] = forms.DecimalField(
                max_digits=6, decimal_places=2, min_value=0, required=False,
                label=f"Annual leave allowance {year.year} (hours)")
            self.fields[f"bank_holiday_{year.year}"] = forms.DecimalField(
                max_digits=6, decimal_places=2, min_value=0, required=False,
                label=f"Bank holiday allowance {year.year} (hours)")

    def clean(self):
        data = super().clean()
        for year in self.years:
            a, b = data.get(f"annual_{year.year}"), data.get(f"bank_holiday_{year.year}")
            if (a is None) != (b is None):
                self.add_error(f"annual_{year.year}", "Give both allowances for the year, or neither.")
        return data

    def allowances(self):
        """[(leave_year, annual, bank_holiday)] for the years both are given."""
        return [(y, self.cleaned_data[f"annual_{y.year}"], self.cleaned_data[f"bank_holiday_{y.year}"])
                for y in self.years if self.cleaned_data.get(f"annual_{y.year}") is not None]

    def year_fields(self):
        """[(annual field, bank holiday field)] per year, for the template."""
        return [(self[f"annual_{y.year}"], self[f"bank_holiday_{y.year}"]) for y in self.years]


class NotesForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea, required=False)


class DepartmentForm(forms.Form):
    name = forms.CharField(max_length=60)
    colour = forms.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR, "Choose a colour.")])
    display_order = forms.IntegerField(min_value=0, initial=100)
    archived = forms.BooleanField(required=False)
