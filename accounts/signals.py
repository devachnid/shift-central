from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .client_ip import client_ip
from .models import LoginEvent


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    LoginEvent.objects.create(user=user, ip=client_ip(request) or "",
                              user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:200])
