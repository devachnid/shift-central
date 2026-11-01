"""The login page (the practice account, or the superuser's password form
when HR is not configured), sign-out that goes on to HR, the holding
page for a sign-in that names no person here, and the sign-in callback."""

import logging

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import render
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

from .oidc import practice_hr_logout_url

log = logging.getLogger(__name__)

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


class CallbackView(OIDCAuthenticationCallbackView):
    """Practice HR's redirect back here, with a callback that may arrive
    twice. On Android the installed app shares Chrome's cookies, and the
    redirect can load in the browser tab and in the app at once: the first
    load spends the state (one use only, so a code cannot be replayed), and
    the second, or any reload of the address, finds it gone. The library
    answers that with a 400. Here nobody is signed in by it either way: a
    signed-in session goes on into the app, and one not yet signed in waits
    a moment for the other load to finish and then goes home, which by then
    is signed in or asks to sign in."""

    def get(self, request):
        state = request.GET.get("state")
        spent = (not request.GET.get("error") and "code" in request.GET and state is not None
                 and state not in request.session.get("oidc_states", {}))
        if not spent:
            return super().get(request)
        log.info("sign-in callback with a spent or unknown state (%s)",
                 "signed in" if request.user.is_authenticated else "not signed in")
        if request.user.is_authenticated:
            return HttpResponseRedirect("/")
        return render(request, "accounts/signing_in.html")
