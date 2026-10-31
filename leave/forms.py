"""The booking forms. `BookingForm` serves Add time off (managers, with the
Advanced tab) and Request time off (staff: no person, requestable types
only, no overrides). `costs()` reads the per-day boxes `cost_<iso>` typed
as H:MM or decimal hours into seconds."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms

from leave.models import Booking, LeaveType
from leave.services import hours
from people.models import Person
from people.services import access

HM = re.compile(r"^(\d{1,3}):([0-5]\d)$")
CHANGE_SUBMITS = ("person", "type", "first_day", "last_day", "part", "start", "finish")


def parse_hours(text):
    text = (text or "").strip()
    if not text:
        return None
    m = HM.match(text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    try:
        seconds = hours.from_hours(Decimal(text.replace("h", "").strip()))
    except (InvalidOperation, ValueError, OverflowError):
        raise forms.ValidationError("Type hours as 7:30 or 7.5") from None
    if seconds < 0:
        raise forms.ValidationError("Type hours as 7:30 or 7.5")
    return seconds


def _paid_select():
    widget = forms.NullBooleanSelect()
    widget.choices = [("unknown", "—"), ("true", "Paid"), ("false", "Unpaid")]
    return widget


class BookingForm(forms.Form):
    person = forms.ModelChoiceField(Person.objects.none(), required=False)
    type = forms.ModelChoiceField(LeaveType.objects.filter(archived=False))
    description = forms.CharField(max_length=80, required=False, label="Display")
    first_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="First day off")
    last_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="Last day off")
    part = forms.ChoiceField(choices=Booking.Part.choices, initial="whole")
    start = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    finish = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    paid = forms.NullBooleanField(required=False, widget=_paid_select())
    staff_note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")
    manager_note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Manager notes")

    def __init__(self, user, data=None, initial=None, person=None, staff=False):
        super().__init__(data, initial=initial)
        self.user, self.staff = user, staff
        if staff:
            del self.fields["person"], self.fields["manager_note"], self.fields["paid"]
            self.fields["type"].queryset = LeaveType.objects.filter(archived=False, requestable=True)
        else:
            del self.fields["staff_note"]
            if person is not None:         # editing: the booking stays with its person
                people = Person.objects.filter(pk=person.pk)
            else:
                people = access.managed_people(user)
                me = getattr(user, "person", None)
                if me is not None:
                    people = people | Person.objects.filter(pk=me.pk)
            self.fields["person"].queryset = people.distinct().order_by("last_name", "first_name")
            self.fields["person"].required = True
        for name in CHANGE_SUBMITS:
            if name in self.fields:
                self.fields[name].widget.attrs["data-submit-on-change"] = ""

    def clean(self):
        d = super().clean()
        if d.get("first_day") and d.get("last_day") and d["last_day"] < d["first_day"]:
            self.add_error("last_day", "The last day is before the first")
        if d.get("part") != "whole" and d.get("first_day") != d.get("last_day"):
            self.add_error("part", "A half day or times is one day")
        if d.get("part") == "times" and not (d.get("start") and d.get("finish") and d["start"] < d["finish"]):
            self.add_error("finish", "Give a start before a finish")
        if d.get("part") != "times":
            d["start"] = d["finish"] = None
        return d

    def booking_kwargs(self):
        d = self.cleaned_data
        return {"leave_type": d["type"], "first": d["first_day"], "last": d["last_day"], "part": d["part"],
                "start": d["start"], "finish": d["finish"], "description": d.get("description", ""), "paid": d.get("paid")}

    def costs(self):
        """{day: seconds} for every cost_<iso> box the manager filled."""
        out = {}
        for key, value in self.data.items():
            if key.startswith("cost_") and value.strip():
                try:
                    out[date.fromisoformat(key[5:])] = parse_hours(value)
                except (ValueError, forms.ValidationError):
                    self.add_error(None, f"Could not read the hours for {key[5:]}")
        return out


class CancelForm(forms.Form):
    note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")


class DecideForm(forms.Form):
    decision = forms.ChoiceField(choices=[("approve", "Approve"), ("decline", "Decline")])
    note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Note")


class AdjustForm(forms.Form):
    leave_year = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    account = forms.ChoiceField(choices=[("annual", "Annual leave"), ("bank_holiday", "Bank holiday allowance"), ("toil", "TOIL")])
    hours = forms.CharField(max_length=12, help_text="Hours to add, e.g. 15:00; a minus sign takes hours away")
    reason = forms.CharField(max_length=300)

    def clean_hours(self):
        text = self.cleaned_data["hours"].strip()
        sign = -1 if text[:1] in ("-", "−") else 1
        seconds = parse_hours(text[1:] if text[:1] in ("-", "−", "+") else text)
        if not seconds:
            raise forms.ValidationError("Type the hours")
        return sign * seconds


class HoursChangeForm(forms.Form):
    from_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="From")
    weekly_hours = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    days_per_week = forms.IntegerField(min_value=1, max_value=7)
    annual_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="New annual leave allowance (full year, hours)")
    bank_holiday_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="New bank holiday allowance (full year, hours)")
    note = forms.CharField(max_length=300, label="Reason")
