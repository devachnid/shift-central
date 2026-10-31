from django import forms

from leave.models import LeaveType


class ConvertForm(forms.Form):
    first_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "data-submit-on-change": ""}, format="%Y-%m-%d"), label="First sick day")
    last_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "data-submit-on-change": ""}, format="%Y-%m-%d"), label="Last sick day")
    type = forms.ModelChoiceField(LeaveType.objects.filter(archived=False, sickness=True), label="Record as")
    note = forms.CharField(max_length=200, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Manager notes")

    def __init__(self, *args, booking=None, **kwargs):
        if booking is not None:
            kwargs.setdefault("initial", {"first_day": booking.first_day, "last_day": booking.last_day,
                                          "type": LeaveType.objects.filter(sickness=True, archived=False).order_by("display_order").first()})
        super().__init__(*args, **kwargs)
        self.booking = booking

    def clean(self):
        d = super().clean()
        if d.get("first_day") and d.get("last_day") and d["last_day"] < d["first_day"]:
            self.add_error("last_day", "The last day is before the first")
        return d
