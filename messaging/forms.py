from django import forms

from people.models import Person, Team


class MessageForm(forms.Form):
    subject = forms.CharField(max_length=150)
    body = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 6}), label="Message")
    people = forms.ModelMultipleChoiceField(Person.objects.none(), required=False, label="People",
                                            widget=forms.SelectMultiple(attrs={"size": 8}))
    teams = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                           widget=forms.CheckboxSelectMultiple)
    everyone = forms.BooleanField(required=False, label="Everyone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["people"].queryset = Person.objects.current().order_by("name")


class NoticeForm(forms.Form):
    title = forms.CharField(max_length=120)
    body = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 8}), label="Text")
    everyone = forms.BooleanField(required=False, label="Everyone")
    teams = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                           widget=forms.CheckboxSelectMultiple, label="Or these teams")
    pinned = forms.BooleanField(required=False, label="Pin to the top")
    show_until = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                                 label="Show until", help_text="Leave empty to keep it up.")
    notify = forms.BooleanField(required=False, label="Also tell staff by email and notification")
