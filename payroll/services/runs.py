"""Mark as sent to the bureau (PAY-02): the snapshot a later report compares
against. All-teams managers only: the bureau's record is the practice's."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from payroll.models import PayrollRun
from payroll.services import report
from people.services import access, audit

DUE_DAYS_BEFORE_END = 10


def latest(month):
    return PayrollRun.objects.filter(month=month).order_by("-sent_at", "-pk").first()


def mark_sent(user, month):
    if not access.is_all_teams(user):
        raise PermissionDenied("only an all-teams manager marks the payroll sent")
    people = report.people_for(user, month)
    rows = report.rows(people, month)
    figures = {"generated_at": timezone.now().isoformat(), "rows": {str(r.person.pk): r.figures() for r in rows}}
    with transaction.atomic():
        run = PayrollRun.objects.create(month=month, sent_by=user, people=len(rows), figures=figures)
        audit.record_as(user, "payroll.payrollrun", run.pk, {"sent": ("", f"{month:%B %Y}, {len(rows)} people")}, note="marked sent to the bureau")
    return run


def unsent_due(user, today=None):
    """This month, when it ends within ten days and has not been marked
    sent; for all-teams managers only (the Health card's line)."""
    if not access.is_all_teams(user):
        return None
    today = today or timezone.localdate()
    month = today.replace(day=1)
    if report.month_end(month) - today > timedelta(days=DUE_DAYS_BEFORE_END):
        return None
    return None if latest(month) else month
