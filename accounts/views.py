"""The login page (the practice account, or the superuser's password form
when HR is not configured), sign-out that goes on to HR, and the holding
page for a sign-in that names no person here."""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .oidc import practice_hr_logout_url

PRACTICE_ACCOUNT_ONLY = "Sign in with the practice account."


class LoginForm(AuthenticationForm):
    """With HR configured every password sign-in is refused here, before
    authenticate() runs, and the refusal reads the same for every address."""

    def clean(self):
        if settings.PRACTICE_HR_URL:
            raise ValidationError(PRACTICE_ACCOUNT_ONLY, code="practice_account")
        return super().clean()


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        id_token = request.session.get("oidc_id_token")
        response = super().post(request, *args, **kwargs)
        onward = practice_hr_logout_url(request, id_token)
        return HttpResponseRedirect(onward) if onward else response


@login_required
def not_on_rota(request):
    """A signed-in account with no Person: HR has not sent them yet, or
    their login is not linked to an employee there."""
    if hasattr(request.user, "person"):
        return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "accounts/not_on_rota.html")
