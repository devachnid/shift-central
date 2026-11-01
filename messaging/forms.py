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
