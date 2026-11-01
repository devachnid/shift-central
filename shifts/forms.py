"""The forms behind the grid's pop-ups. The shift form turns itself into the
JSON-shaped item entries.set_cell takes, so the dialog and the grid's API
share one writer and one set of rules."""

from django import forms

from people.models import Department, Team
from people.services import access
from shifts.models import Entry
from shifts.services import options as options_service

BREAK_CHOICES = [(0, "None"), (15, "15 minutes"), (30, "30 minutes"), (45, "45 minutes"), (60, "1 hour")]


class ShiftForm(forms.Form):
    start = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    finish = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    break_minutes = forms.TypedChoiceField(choices=BREAK_CHOICES, coerce=int, initial=0)
    department = forms.ModelChoiceField(Department.objects.filter(archived=False), required=False, empty_label="None")
    text = forms.CharField(max_length=200, required=False, label="Comment")
    wfh = forms.BooleanField(required=False, label="Working from home")
    overtime = forms.ChoiceField(choices=Entry.Overtime.choices, required=False, initial="")

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("finish") and data["finish"] <= data["start"]:
            self.add_error("finish", "The finish must be after the start.")
        return data

    def item(self):
        d = self.cleaned_data
        return {"kind": "shift", "start": d["start"].strftime("%H:%M"), "finish": d["finish"].strftime("%H:%M"),
                "break_minutes": d["break_minutes"], "department": d["department"].pk if d["department"] else None,
                "text": d["text"], "wfh": d["wfh"], "overtime": d["overtime"] or ""}


class OptionsForm(forms.Form):
    staff_colours = forms.BooleanField(required=False, label="Show staff colours")
    job_titles = forms.BooleanField(required=False, label="Show job titles")
    department_colours = forms.BooleanField(required=False, label="Use department colours for shifts")
    float_headers = forms.BooleanField(required=False, label="Float dates and names when scrolling")
    my_shifts_on_top = forms.BooleanField(required=False, label="My shifts on top")
    only_my_shifts = forms.BooleanField(required=False, label="Only my shifts")
    hide_no_shifts = forms.BooleanField(required=False, label="Hide staff with no shifts")
    font_size = forms.ChoiceField(choices=[(k, k) for k in options_service.CHOICES["font_size"]], initial="md")
    spacing = forms.ChoiceField(choices=[(k, k) for k in options_service.CHOICES["spacing"]], initial="normal",
                                required=False)
    days = forms.MultipleChoiceField(choices=list(enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])),
                                     widget=forms.CheckboxSelectMultiple, required=False, label="Days to display")
    paste = forms.ChoiceField(choices=[("replace", "Replace what is there"), ("add", "Add to what is there")],
                              label="Paste behaviour")


class TemplateForm(forms.Form):
    name = forms.CharField(max_length=80)


class ReplaceForm(forms.Form):
    cells = forms.CharField(widget=forms.HiddenInput)
    find = forms.CharField(max_length=200)
    replace = forms.CharField(max_length=200, required=False, label="Replace with")
    match_case = forms.BooleanField(required=False)


OVERTIME_CHOICES = [("", "Normal hours"), ("paid", "Overtime – paid"), ("toil", "Overtime – TOIL")]


class OpenShiftForm(forms.Form):
    team = forms.ModelChoiceField(Team.objects.none(), label="Owning team",
                                  help_text="Its managers approve the claims.")
    day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    start = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    finish = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    break_minutes = forms.TypedChoiceField(choices=BREAK_CHOICES, coerce=int, initial=0, label="Break")
    department = forms.ModelChoiceField(Department.objects.filter(archived=False), required=False, empty_label="None")
    comment = forms.CharField(max_length=200, required=False)
    everyone = forms.BooleanField(required=False, label="Offer it to everyone")
    audience = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                              widget=forms.CheckboxSelectMultiple, label="Or to these teams")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = access.managed_teams(user).filter(active=True)


class ClaimForm(forms.Form):
    overtime = forms.ChoiceField(choices=OVERTIME_CHOICES, required=False, initial="", widget=forms.RadioSelect)
    note = forms.CharField(max_length=200, required=False, label="Note for the manager")


class DecideForm(forms.Form):
    overtime = forms.ChoiceField(choices=OVERTIME_CHOICES, required=False, widget=forms.RadioSelect)
