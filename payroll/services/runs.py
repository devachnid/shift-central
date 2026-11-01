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


def _figures(rows):
    return {"generated_at": timezone.now().isoformat(), "rows": {str(r.person.pk): r.figures() for r in rows}}


def mark_sent(user, month):
    """Records what the bureau has now been told for every month the report
    covered: the month itself as it stands, and each earlier sent month of
    the twelve whose figures have changed since (the report's corrections),
    as a fresh run with today's figures. The next report compares with that,
    so a correction is sent once."""
    if not access.is_all_teams(user):
        raise PermissionDenied("only an all-teams manager marks the payroll sent")
    rows = report.rows(report.people_for(user, month), month)
    corrected = []
    for past, old in report.lookback(month):
        sent, now = report.recompute(past, old)
        if report.differences(past, sent, now):
            corrected.append((past, list(now.values())))
    with transaction.atomic():
        sent_at = timezone.now()
        run = PayrollRun.objects.create(month=month, sent_at=sent_at, sent_by=user, people=len(rows), figures=_figures(rows))
        for past, past_rows in corrected:
            PayrollRun.objects.create(month=past, sent_at=sent_at, sent_by=user, people=len(past_rows), figures=_figures(past_rows))
        note = "marked sent to the bureau"
        if corrected:
            note += ", with corrections to " + ", ".join(f"{past:%B %Y}" for past, _ in corrected)
        audit.record_as(user, "payroll.payrollrun", run.pk, {"sent": ("", f"{month:%B %Y}, {len(rows)} people")}, note=note)
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
