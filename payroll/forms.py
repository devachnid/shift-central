from django import forms


class MonthForm(forms.Form):
    month = forms.CharField(required=False)
