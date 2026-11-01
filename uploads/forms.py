from django import forms


class UploadForm(forms.Form):
    title = forms.CharField(max_length=120, required=False, help_text="Leave empty to use the file's name.")
    file = forms.FileField()
