"""Login accounts. Nobody has a password here but the superuser: everyone
signs in with the practice account (accounts/oidc.py)."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required")
        # Stored as typed, as in the rota: the HR address is what people
        # recognise, and the case-insensitive constraint on User is what
        # keeps two spellings from becoming two accounts.
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        """The login lookup — ModelBackend calls this with whatever was
        typed. An address is not case-sensitive to anyone who uses one, so
        neither is this; the constraint below is what makes `get` safe."""
        return self.get(email__iexact=email)

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    # HR's `admin` claim for this app, set at every sign-in: the practice
    # manager and the assistant managers (spec, section 2).
    is_all_teams_manager = models.BooleanField(
        "all-teams manager", default=False,
        help_text="Set on Practice HR: Login accounts › Apps › Admin of shift-central. "
                  "Updated at each sign-in.")
    # HR's `sub`, stored at the first sign-in; later sign-ins match on it.
    oidc_sub = models.CharField(
        "practice account id", max_length=255, blank=True, default="", db_index=True)
    # HR's `employee_id` claim, set at every sign-in. Kept so a sign-in that
    # arrives before the sync has sent the person can be bound to them on a
    # later request (config/middleware.py), not only at the next sign-in.
    hr_employee_id = models.PositiveIntegerField(
        "Practice HR employee id", null=True, blank=True,
        help_text="From Practice HR at each sign-in.")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = "login account"
        verbose_name_plural = "login accounts"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique",
                                    violation_error_message="A login with this email exists."),
        ]

    def save(self, *args, **kwargs):
        # is_staff keeps Django's meaning, "can open the admin": superusers only.
        self.is_staff = self.is_superuser
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class LoginEvent(models.Model):
    """One row per sign-in (ACC-07). Never deleted in this release."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_events")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.CharField(max_length=45, blank=True, default="")
    user_agent = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-at"]
