"""The booking forms. `BookingForm` serves Add time off (managers, with the
Advanced tab) and Request time off (staff: no person, requestable types
only, no overrides). `costs()` reads the per-day boxes `cost_<iso>` typed
as H:MM or decimal hours into seconds."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django import forms
from django.db.models import Q

from leave.models import BankHoliday, Booking, LeaveType
from leave.services import hours, types
from people.models import Person, Team
from people.services import access

HM = re.compile(r"^([0-9]{1,3}):([0-5][0-9])$")
DECIMAL_HOURS = re.compile(r"^([0-9]+(?:\.[0-9]+)?)\s*h?$")
MAX_DAY = 24 * 3600                 # a day's allowance used
MAX_ADJUSTMENT = 2000 * 3600        # an adjustment, either way
CHANGE_SUBMITS = ("person", "type", "first_day", "last_day", "part", "start", "finish")


def parse_hours(text):
    """Hours as typed in a box, to whole seconds: H:MM ("7:30") or decimal
    hours with an optional h ("7.5", "7.5 h"); blank is None. Anything else
    ("7h30", "1e3", a sign) is refused rather than guessed at."""
    text = (text or "").strip()
    if not text:
        return None
    m = HM.match(text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    m = DECIMAL_HOURS.match(text)
    if m is None or len(m.group(1)) > 12:
        raise forms.ValidationError("Type hours as 7:30 or 7.5")
    try:
        return hours.from_hours(Decimal(m.group(1)))
    except (InvalidOperation, ArithmeticError, ValueError):
        raise forms.ValidationError("Type hours as 7:30 or 7.5") from None


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
                    day, seconds = date.fromisoformat(key[5:]), parse_hours(value)
                except (ValueError, forms.ValidationError):
                    self.add_error(None, f"Could not read the hours for {key[5:]}")
                    continue
                if seconds > MAX_DAY:
                    self.add_error(None, f"A day has 24 hours: check the hours for {key[5:]}")
                    continue
                out[day] = seconds
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
        if seconds > MAX_ADJUSTMENT:
            raise forms.ValidationError("An adjustment is at most 2000 hours either way")
        return sign * seconds


class HoursChangeForm(forms.Form):
    from_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="From")
    weekly_hours = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    days_per_week = forms.IntegerField(min_value=1, max_value=7)
    annual_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="New annual leave allowance (full year, hours)")
    bank_holiday_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="New bank holiday allowance (full year, hours)")
    note = forms.CharField(max_length=300, label="Reason")


class BankHolidayForm(forms.Form):
    day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    name = forms.CharField(max_length=60)

    def clean_day(self):
        day = self.cleaned_data["day"]
        existing = BankHoliday.objects.filter(day=day).first()
        if existing is not None:
            raise forms.ValidationError(f"{existing.name} is already on the list for that day")
        return day


class BlackoutForm(forms.Form):
    first_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="First day")
    last_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="Last day")
    teams = forms.ModelMultipleChoiceField(Team.objects.none(), required=False, widget=forms.CheckboxSelectMultiple,
                                           help_text="Leave none ticked for everyone")
    note = forms.CharField(max_length=120, required=False)

    def __init__(self, *args, row=None, **kwargs):
        super().__init__(*args, **kwargs)
        # An edit keeps the teams the blackout already names, active or not.
        keep = row.teams.values("pk") if row is not None else []
        self.fields["teams"].queryset = Team.objects.filter(Q(active=True) | Q(pk__in=keep))

    def clean(self):
        d = super().clean()
        if d.get("first_day") and d.get("last_day") and d["last_day"] < d["first_day"]:
            self.add_error("last_day", "The last day is before the first")
        return d


class TypeForm(forms.Form):
    """A leave type. What a type draws from and how it reaches payroll decide
    the arithmetic and spec 4's report: they are fixed on a seeded type and,
    for a type a manager added, once it has a booking. Until then they are
    offered, and always when adding."""
    name = forms.CharField(max_length=60)
    colour = forms.RegexField(r"^#[0-9A-Fa-f]{6}$", max_length=7, widget=forms.TextInput(attrs={"type": "color"}),
                              error_messages={"invalid": "Choose a colour"})
    draws_from = forms.ChoiceField(choices=LeaveType.Account.choices, initial="none", label="Takes its days from")
    on_payroll = forms.ChoiceField(choices=LeaveType.Payroll.choices, initial="never", label="On the payroll report")
    requestable = forms.BooleanField(required=False, label="Staff can request it")
    paid_choice = forms.BooleanField(required=False, label="The manager chooses paid or unpaid")
    default_paid = forms.BooleanField(required=False, initial=True, label="Paid unless chosen otherwise")
    display_order = forms.IntegerField(min_value=0, max_value=9999, required=False)
    archived = forms.BooleanField(required=False, label="Archived (no longer offered; its bookings stand)")

    def __init__(self, *args, row=None, **kwargs):
        if row is not None:
            kwargs.setdefault("initial", {k: getattr(row, k) for k in (
                "name", "colour", "draws_from", "on_payroll", "requestable", "paid_choice", "default_paid", "display_order", "archived")})
        super().__init__(*args, **kwargs)
        self.row = row
        if row is None:
            del self.fields["display_order"], self.fields["archived"]
        elif row.seeded or row.bookings.exists():
            del self.fields["draws_from"], self.fields["on_payroll"]

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if LeaveType.objects.filter(name__iexact=name).exclude(pk=self.row.pk if self.row else None).exists():
            raise forms.ValidationError("There is already a type with that name")
        return name

    def save(self, user):
        d = self.cleaned_data
        if self.row is None:
            return types.add(user, d["name"], d["colour"], d["draws_from"], d["requestable"], d["paid_choice"], d["on_payroll"], d["default_paid"])
        fields = {k: d[k] for k in ("name", "colour", "requestable", "paid_choice", "default_paid", "archived")}
        if d.get("display_order") is not None:
            fields["display_order"] = d["display_order"]
        for k in ("draws_from", "on_payroll"):
            if k in d:
                fields[k] = d[k]
        return types.update(user, self.row, **fields)


class SettingsForm(forms.Form):
    reminder_working_days = forms.IntegerField(min_value=1, max_value=30, label="Remind the managers when a request has waited this many working days")
