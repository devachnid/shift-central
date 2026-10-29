"""Sign in with the practice account: Practice HR is the OpenID Connect
provider.

Who a sign-in is: HR's `sub`, once seen. The first time, the `email` claim
is matched to a user not yet bound to a sub, case-insensitively; every
later sign-in matches on `sub` alone, so an email edited on the HR side
cannot move someone into another account (the rota's rule, kept).

Which person they are: HR's `employee_id` names the Person with that
hr_employee_id (people/models/person.py). It is applied at every sign-in:
the person is bound to this user and taken from any other. The id is also
kept on the user, so a person the sync sends later is bound on the next
page load (bind_waiting_person, called by config/middleware.py).

All-teams manager is HR's `admin` claim for this client, set at every
sign-in; only a JSON true counts."""

from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User


class PracticeAccountBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        sub = str(claims.get("sub") or "")
        email = claims.get("email")
        if sub and User.objects.filter(oidc_sub=sub).exists():
            return User.objects.filter(oidc_sub=sub)
        if email:
            return User.objects.filter(email__iexact=email, oidc_sub="")
        return User.objects.none()

    def create_user(self, claims):
        if User.objects.filter(email__iexact=claims["email"]).exists():
            raise SuspiciousOperation("practice-account sign-in refused: the email belongs "
                                      "to an account this sign-in may not use")
        user = User(email=claims["email"], oidc_sub=str(claims.get("sub") or ""),
                    is_all_teams_manager=_is_admin(claims), hr_employee_id=_employee_id(claims))
        user.set_unusable_password()
        user.save()
        _bind_person(user, claims)
        return user

    def update_user(self, user, claims):
        changed = []
        sub = str(claims.get("sub") or "")
        if sub and not user.oidc_sub:
            user.oidc_sub = sub
            changed.append("oidc_sub")
        if user.is_all_teams_manager != _is_admin(claims):
            user.is_all_teams_manager = _is_admin(claims)
            changed.append("is_all_teams_manager")
        if user.hr_employee_id != _employee_id(claims):
            user.hr_employee_id = _employee_id(claims)
            changed.append("hr_employee_id")
        if changed:
            user.save(update_fields=changed)
        _bind_person(user, claims)
        return user


def _is_admin(claims):
    return claims.get("admin") is True


def _employee_id(claims):
    """HR's employee_id when it is a whole number (a JSON true is not), else None."""
    value = claims.get("employee_id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _bind_person(user, claims):
    """Person.user follows HR's employee_id. Nothing happens when the claim
    is missing or names nobody here yet; the next hr_sync usually resolves
    that, bind_waiting_person binds them on the next page load, and the
    holding page (accounts/views.py) says so meanwhile."""
    from people.models import Person
    employee_id = _employee_id(claims)
    if employee_id is None:
        return
    try:
        person = Person.objects.get(hr_employee_id=employee_id)
    except Person.DoesNotExist:
        return
    if person.user_id == user.pk:
        return
    Person.objects.filter(user=user).exclude(pk=person.pk).update(user=None)
    person.user = user
    person.save(update_fields=["user"])


def bind_waiting_person(user):
    """Bind the person HR's employee id names to a signed-in user who has
    none, when the sync has since brought them, so the holding page resolves
    by itself. Only an unbound person is taken here: moving a person from
    another user is left to a sign-in, which carries HR's fresh claim.
    Returns the person, or None."""
    from people.models import Person
    if user.hr_employee_id is None:
        return None
    person = Person.objects.filter(hr_employee_id=user.hr_employee_id, user__isnull=True).first()
    if person is None:
        return None
    person.user = user
    person.save(update_fields=["user"])
    user.person = person        # replaces the cached "no person" on this request's user
    return person


def practice_hr_logout_url(request, id_token=None):
    """HR's RP-initiated logout, so signing out here ends the HR session
    too — on a shared PC the next person must not be signed straight in."""
    if not settings.PRACTICE_HR_URL:
        return None
    params = {"post_logout_redirect_uri": request.build_absolute_uri(settings.LOGIN_URL),
              "client_id": settings.OIDC_RP_CLIENT_ID}
    if id_token:
        params["id_token_hint"] = id_token
    return f"{settings.PRACTICE_HR_URL}/o/logout/?{urlencode(params)}"
