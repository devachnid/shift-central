"""seed_demo: fictional working data for a staging box, after hr_sync. The
Person rows are built here by the factories, as hr_sync would leave them."""

from datetime import date, time, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from accounts.models import User
from leave.models import Booking, BookingDay
from leave.services import balances, years
from messaging.models import Message, Notice, Outbox
from people.management.commands.seed_demo import ACTOR_EMAIL, CAST, REQUESTER_EMAIL
from people.models import Allowance, AuditEntry, Person, TeamManager
from people.services import health
from shifts.models import DayChange, Entry, OpenShift, OpenShiftClaim
from shifts.services import open_shifts
from shifts.services.open_shifts import OpenShiftError
from uploads.models import UploadedFile
from tests.factories import (make_allowance, make_bank_holiday, make_entry, make_gp_session, make_person, make_team, make_type,
                             make_user_for)

pytestmark = pytest.mark.django_db
BASE = "tom@example.org"
ARGS = {"email_base": BASE, "yes_this_is_staging": True}


def seed(**kw):
    out = StringIO()
    call_command("seed_demo", stdout=out, **{**ARGS, **kw})
    return out.getvalue()


def email(member, base=BASE):
    return member.email(base)


@pytest.fixture
def people():
    """The cast as hr_sync leaves them: names, emails, teams, GPs, and nothing typed."""
    out = {}
    for m in CAST:
        out[(m.first, m.last)] = make_person(first_name=m.first, last_name=m.last, email=email(m),
                                             team=make_team(m.team), is_gp=m.gp)
    return out


def tables():
    """Row counts of everything the command may write."""
    return {model.__name__: model.objects.count()
            for model in (Person, Allowance, AuditEntry, TeamManager, Entry, DayChange, Booking, BookingDay, Outbox, User)}


@pytest.fixture
def manager(db):
    return User.objects.create_user(email="boss@example.org", is_all_teams_manager=True)


# --- the cast ---------------------------------------------------------------

def test_the_cast_is_nineteen_with_the_documented_addresses():
    assert len(CAST) == 19
    by_name = {(m.first, m.last): m for m in CAST}
    assert by_name[("Morgan", "Ellis")].email(BASE) == "tom+morgan.ellis@example.org"
    assert by_name[("Tomasz", "Kowal")].email(BASE) == "tom+tomasz.kowal@example.org"
    assert sum(m.gp for m in CAST) == 3
    assert len({m.email(BASE) for m in CAST}) == 19


# --- refusals: nothing changes -------------------------------------------------

def test_it_refuses_without_the_staging_flag(people):
    before = tables()
    with pytest.raises(CommandError, match="--yes-this-is-staging"):
        seed(yes_this_is_staging=False)
    assert tables() == before


def test_it_refuses_without_an_email_base(people):
    before = tables()
    with pytest.raises(CommandError, match="--email-base"):
        call_command("seed_demo", yes_this_is_staging=True, stdout=StringIO())
    assert tables() == before


@pytest.mark.parametrize("base", ["tom+x@example.org", "a@b@example.org", "tom.example.org", "@example.org", "tom@"])
def test_it_refuses_a_base_that_is_not_local_at_domain(people, base):
    before = tables()
    with pytest.raises(CommandError, match="--email-base"):
        seed(email_base=base)
    assert tables() == before


def test_it_refuses_when_the_cast_is_incomplete_and_says_run_hr_sync(people):
    Person.objects.get(email=email(CAST[7])).delete()
    Person.objects.get(email=email(CAST[9])).delete()
    before = tables()
    with pytest.raises(CommandError) as error:
        seed()
    assert "hr_sync" in str(error.value) and "2 of the 19" in str(error.value)
    assert tables() == before and not Allowance.objects.exists()


def test_it_refuses_an_empty_database():
    with pytest.raises(CommandError, match="19 of the 19 people are missing: run hr_sync"):
        seed()


def test_it_refuses_when_the_base_is_not_the_one_the_seeds_used(people):
    with pytest.raises(CommandError, match="hr_sync"):
        seed(email_base="other@example.org")


def test_it_refuses_with_a_person_outside_the_cast(people):
    make_person(first_name="Stranger", last_name="Danger", email="stranger@example.org", team=make_team("Reception"))
    before = tables()
    with pytest.raises(CommandError, match="1 person row outside the cast"):
        seed()
    assert tables() == before


def test_it_refuses_when_a_gp_is_not_marked_as_one(people):
    Person.objects.filter(email=email(CAST[8])).update(is_gp=False)
    before = tables()
    with pytest.raises(CommandError, match="GP"):
        seed()
    assert tables() == before


def test_a_refusal_names_no_one(people):
    make_person(first_name="Stranger", last_name="Danger", email="stranger@example.org", team=make_team("Reception"))
    with pytest.raises(CommandError) as error:
        seed()
    assert "stranger" not in str(error.value).lower() and "example.org" not in str(error.value)


# --- what it seeds ----------------------------------------------------------------

def test_people_get_hours_allowances_display_settings_and_the_two_team_grants(people, manager):
    typed = people[("Rosa", "Delgado")]
    typed.job_title = "Front of house lead"
    typed.save()
    assert health.figures(manager)["needs_setup"].count() == 16       # sixteen non-GPs need setting up
    out = seed()
    today = date(2026, 11, 2)
    for m in CAST:
        person = Person.objects.get(email=email(m))
        if m.gp:
            assert person.weekly_hours is None and person.days_per_week is None       # sessions, not hours
            continue
        assert (person.weekly_hours, person.days_per_week) == (m.weekly, m.days)
        for year in years.years_for(person, today):
            row = person.allowances.get(leave_year=year)
            assert row.annual_hours == m.weekly * 5 and row.bank_holiday_hours == m.weekly * Decimal("1.6")
    assert list(health.figures(manager)["needs_setup"]) == []                           # the Health card's box is empty
    assert Person.objects.get(email=email(CAST[0])).job_title == "Practice Manager"
    assert Person.objects.get(email=email(CAST[3])).job_title == "Front of house lead"   # a typed one is kept
    assert Person.objects.get(email=email(CAST[4])).name_colour == "#2F6FB3"
    grants = {(r.person.name, r.team.name) for r in TeamManager.objects.select_related("person", "team")}
    assert grants == {("Fiona Marsh", "Nursing"), ("Hamid Qureshi", "Pharmacy")}
    # no one is made an all-teams manager: that is Practice HR's box, applied at sign-in
    assert not User.objects.filter(is_all_teams_manager=True).exclude(email__in=[ACTOR_EMAIL, manager.email]).exists()
    assert "Admin of shift-central" in out and "nothing was done for them here" in out
    for m in CAST:                               # the summary gives counts, never a name or an address
        assert m.first not in out and m.last not in out
    assert "example.org" not in out and "tom+" not in out and "No email was sent and none was queued." in out
    actor = User.objects.get(email=ACTOR_EMAIL)
    assert not actor.is_active and not actor.has_usable_password() and not hasattr(actor, "person")
    assert AuditEntry.objects.filter(field="manager_of", actor_email=ACTOR_EMAIL).count() == 2
    assert AuditEntry.objects.filter(model="people.allowance", actor_email=ACTOR_EMAIL).count() == 16 * 2 * 2


def test_the_rota_covers_five_weeks_on_each_persons_own_days_and_queues_nothing_to_notify(people, manager):
    from shifts.services import notify
    make_bank_holiday(date(2026, 11, 17), "A made-up bank holiday")
    seed()
    this = date(2026, 11, 2)
    window = Entry.objects.filter(day__range=(this, this + timedelta(days=34)))
    assert window.filter(day__week_day__in=(1, 7)).count() == 0                  # no Sunday, no Saturday
    assert not window.filter(day=date(2026, 11, 17)).exists()                      # nobody on a bank holiday
    assert not Entry.objects.filter(person__is_gp=True).exists()
    assert Entry.objects.filter(day__gt=this + timedelta(days=34)).exists()        # and the weeks the bookings fall in

    def per_week(name, week):
        return Entry.objects.filter(person__name=name, day__range=(this + timedelta(weeks=week), this + timedelta(weeks=week, days=6))).count()
    assert [per_week("Tomasz Kowal", w) for w in range(5)] == [2, 2, 1, 2, 2]     # Tuesdays and Thursdays; the 17th is a Tuesday
    assert per_week("Aisha Rahman", 0) == 3 and per_week("Rosa Delgado", 0) == 5 and per_week("Rosa Delgado", 2) == 4
    assert per_week("Morgan Ellis", 0) == 0                                       # managers are off the seeded rota
    rota = Entry.objects.filter(person__team__name="Reception").exclude(pk__in=OpenShift.objects.filter(entry__isnull=False).values("entry"))
    shifts = set(rota.values_list("start", "finish"))                             # the filled open shift is not part of the rota pattern
    assert {(s.strftime("%H:%M"), f.strftime("%H:%M")) for s, f in shifts} == {("08:00", "16:15"), ("10:15", "18:30")}
    first = {n: Entry.objects.get(person__name=n, day=this).start.hour for n in ("Sophie Brennan", "Liam Doyle")}
    assert sorted(first.values()) == [8, 10]                                      # the desk is covered at both ends
    nurse = Entry.objects.filter(person__name="Fiona Marsh").first()
    assert (nurse.start.strftime("%H:%M"), nurse.finish.strftime("%H:%M")) == ("08:30", "17:00") and nurse.department.name == "Nursing"
    assert AuditEntry.objects.filter(model="shifts.entry", actor_email=ACTOR_EMAIL).exists()
    # the seeded rota is the starting point: nothing is left for Notify staff to email
    assert not DayChange.objects.exists() and notify.pending(manager) == []
    assert AuditEntry.objects.filter(field="baseline", actor_email=ACTOR_EMAIL).exists()


def test_gp_sessions_and_gp_leave_are_left_alone(people):
    session = make_gp_session(people[("Priya", "Nair")], date(2026, 11, 3))
    seed()
    assert list(Entry.objects.filter(person__is_gp=True)) == [] and not Booking.objects.filter(person__is_gp=True).exists()
    assert type(session).objects.filter(pk=session.pk).exists()


def test_bookings_have_the_right_statuses_costs_and_audit(people, manager):
    aisha_user = make_user_for(people[("Aisha", "Rahman")])
    out = seed()
    assert "9 bookings made (7 approved, 1 waiting for a decision, 1 cancelled), 0 left out" in out
    assert Booking.objects.count() == 9 and not Booking.objects.filter(person__is_gp=True).exists()

    sophie = Booking.objects.get(person__name="Sophie Brennan", type__name="Holiday")
    assert (sophie.first_day, sophie.last_day, sophie.status) == (date(2026, 12, 7), date(2026, 12, 11), "approved")   # next month, Monday to Friday
    liam = Booking.objects.get(person__name="Liam Doyle")
    assert (liam.first_day.weekday(), (liam.last_day - liam.first_day).days, liam.status) == (0, 4, "approved")
    grace = Booking.objects.get(person__name="Grace Tanaka")
    assert (grace.first_day, grace.last_day, grace.status, grace.type.name) == (date(2026, 11, 17), date(2026, 11, 17), "approved", "Holiday")
    elena = Booking.objects.get(person__name="Elena Fischer")
    assert (elena.part, elena.status, elena.type.name) == ("pm", "approved", "Holiday")
    aisha = Booking.objects.get(person__name="Aisha Rahman")
    assert aisha.status == "approved" and aisha.decided_by.email == ACTOR_EMAIL and aisha.requested_by_id == aisha_user.pk
    ines = Booking.objects.get(person__name="Ines Costa")
    assert ines.status == "pending" and not BookingDay.objects.filter(booking=ines).exists()
    sick = Booking.objects.get(person__name="Sophie Brennan", type__name="Sick leave")
    assert sick.status == "approved" and not sick.dates_only and (sick.first_day.month, sick.last_day.month) == (10, 10)
    past = Booking.objects.get(person__name="Doreen Hughes")
    assert past.dates_only and past.status == "approved" and past.last_day < date(2026, 11, 2)
    assert not BookingDay.objects.filter(booking=past).exists()
    owen = Booking.objects.get(person__name="Owen Pryce")
    assert owen.status == "cancelled"
    assert Entry.objects.filter(person=owen.person, day=owen.first_day).get().covered_by is None   # its shift is back

    # costed from the rota, never an "average day" to check, and nobody over their allowance
    assert not BookingDay.objects.filter(placeholder=True).exists()
    week = BookingDay.objects.filter(booking=sophie)
    assert week.count() == 5 and {bd.cost_seconds for bd in week} == {27000} and {bd.source for bd in week} == {"rota"}
    assert [bd.cost_seconds for bd in BookingDay.objects.filter(booking=liam).order_by("day")] == [27000] * 4 + [0]
    assert Entry.objects.filter(person=sophie.person, day=date(2026, 12, 8), covered_by__isnull=False).count() == 1   # hidden under the leave
    for person in Person.objects.filter(is_gp=False):
        for year in years.years_for(person, date(2026, 11, 2)):
            statement = balances.statement(person, year)
            assert not statement.missing and statement.annual_remaining >= 0 and statement.annual_available >= 0
    figures = health.figures(manager)
    assert figures["placeholder_count"] == 0 and figures["negative"] == [] and figures["waiting"] == 1

    # the Activity log: the seeding manager, and the person who "asked"
    mine = AuditEntry.objects.filter(actor_email=ACTOR_EMAIL)
    assert {"people.person", "people.allowance", "shifts.entry", "leave.booking"} <= set(mine.values_list("model", flat=True))
    assert mine.filter(model="leave.booking", note="cancelled by a manager").count() == 1
    assert mine.filter(model="leave.booking", note="approved").count() == 1
    assert AuditEntry.objects.filter(model="leave.booking", actor_email=aisha_user.email).count() == 1
    assert AuditEntry.objects.filter(model="leave.booking", actor_email=REQUESTER_EMAIL).count() == 1     # Ines's, by the throwaway login

    # the throwaway login is gone and a real one is left alone
    assert set(User.objects.values_list("email", flat=True)) == {ACTOR_EMAIL, aisha_user.email, "boss@example.org"}
    assert Person.objects.get(name="Aisha Rahman").user_id == aisha_user.pk
    assert Person.objects.get(name="Ines Costa").user_id is None


# --- idempotent ---------------------------------------------------------------------

def test_a_second_run_changes_nothing_and_does_not_error(people):
    seed()
    before = tables()
    rows = lambda: list(Entry.objects.order_by("pk").values_list("pk", "person_id", "day", "start", "finish", "covered_by_id"))  # noqa: E731
    snapshot = rows()
    out = seed()
    assert tables() == before and rows() == snapshot
    assert "Nothing to do" in out and "No email was sent" in out


def test_a_later_run_adds_only_the_weeks_that_came_into_range_and_no_second_set_of_bookings(people, today):
    seed()
    bookings_before, entries_before = Booking.objects.count(), Entry.objects.count()
    today(date(2026, 11, 30))                    # the window now reaches Dec 28: two weeks past the ones already written
    seed()
    assert Booking.objects.count() == bookings_before
    assert Entry.objects.count() > entries_before and not DayChange.objects.exists()


def test_what_a_manager_typed_is_not_overwritten_and_does_not_stop_the_run(people):
    nurse = people[("Grace", "Tanaka")]
    nurse.weekly_hours, nurse.days_per_week = Decimal("32"), 4
    nurse.save()
    make_allowance(nurse, date(2026, 1, 1), Decimal("100"), Decimal("20"))
    make_entry(people[("Sophie", "Brennan")], date(2026, 11, 3), start=time(7), finish=time(9))
    seed()
    nurse.refresh_from_db()
    assert nurse.weekly_hours == Decimal("32") and nurse.allowances.get(leave_year=date(2026, 1, 1)).annual_hours == Decimal("100")
    assert nurse.allowances.get(leave_year=date(2027, 1, 1)).annual_hours == Decimal("30") * 5      # the missing year is filled
    assert Entry.objects.filter(person__name="Sophie Brennan", day__range=(date(2026, 11, 2), date(2026, 11, 8))).count() == 1


# --- no mail --------------------------------------------------------------------------

@pytest.mark.parametrize("host", ["smtp.example.org", ""])
def test_nothing_is_sent_and_nothing_is_queued(people, settings, host, django_capture_on_commit_callbacks):
    from django.db import transaction
    from leave.services import bookings
    from messaging import services
    settings.EMAIL_HOST = host
    send, on_commit = services.send, transaction.on_commit
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        seed()
    assert callbacks == []                       # not one send was left waiting for the commit
    assert mail.outbox == []
    assert Outbox.objects.count() == 0           # no "sent", and no "mail not configured" row to be mistaken for a failure
    assert services.send is send and transaction.on_commit is on_commit            # both seams are put back
    # ...and the ordinary path is as it was: a request now reaches the managers (once someone can be told)
    make_user_for(people[("Morgan", "Ellis")], is_all_teams_manager=True)
    sam = people[("Tomasz", "Kowal")]
    with django_capture_on_commit_callbacks(execute=True):
        bookings.request(make_user_for(sam), sam, make_type("Holiday"), date(2026, 12, 2), date(2026, 12, 2), "whole")
    assert Outbox.objects.count() == 1


# --- other days -----------------------------------------------------------------------

@pytest.mark.parametrize("day", [date(2026, 11, 1), date(2026, 12, 20), date(2027, 1, 5)])
def test_it_seeds_cleanly_on_other_days(people, today, manager, day):
    """A Sunday; a month before Christmas weeks and a new year; early January, when "last month" is the leave year before."""
    today(day)
    seed()
    assert list(health.figures(manager)["needs_setup"]) == []
    assert not BookingDay.objects.filter(placeholder=True).exists()
    assert Booking.objects.filter(status="pending").count() == 1
    assert Outbox.objects.count() == 0 and not DayChange.objects.exists()
    before = tables()
    seed()
    assert tables() == before


# --- engagement (spec 5) --------------------------------------------------------

@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    """The sample document is written under MEDIA_ROOT: keep every seed run out of the real one."""
    settings.MEDIA_ROOT = tmp_path / "media"


def engagement():
    return {m.__name__: m.objects.count() for m in (OpenShift, OpenShiftClaim, Notice, Message, UploadedFile)}


def test_it_seeds_open_shifts_notices_a_message_and_a_document(people, media):
    seed()
    assert engagement() == {"OpenShift": 3, "OpenShiftClaim": 2, "Notice": 2, "Message": 1, "UploadedFile": 1}
    assert OpenShift.objects.filter(state="filled").count() == 1
    assert OpenShiftClaim.objects.filter(state="waiting").count() == 1
    filled = OpenShift.objects.get(state="filled")
    assert Entry.objects.filter(person=filled.filled_by, day=filled.day, start=filled.start).exists()


def test_the_engagement_seed_sends_no_mail_and_queues_no_push(people, media, push_on):
    from tests.factories import make_push_device
    make_push_device(next(iter(people.values())))
    seed()
    assert Outbox.objects.count() == 0 and not mail.outbox


def test_a_second_run_adds_no_engagement_rows(people, media):
    seed()
    before = engagement()
    seed()
    assert engagement() == before


def test_the_report_mentions_the_engagement_rows(people, media):
    assert "open shifts" in seed()


def test_a_refused_approval_leaves_the_claim_waiting_and_the_seed_completes(people, media, monkeypatch):
    def refuse(user, claim, *args, **kwargs):
        raise OpenShiftError("Liam Doyle is on leave that day.")
    monkeypatch.setattr(open_shifts, "approve", refuse)
    report = seed()
    phones = OpenShift.objects.get(comment="demo data: phones")
    assert phones.state == "open" and phones.filled_by is None
    assert phones.claims.get().state == "waiting" and phones.claims.get().person.first_name == "Liam"
    assert engagement() == {"OpenShift": 3, "OpenShiftClaim": 2, "Notice": 2, "Message": 1, "UploadedFile": 1}
    assert not OpenShift.objects.filter(state="filled").exists()
    assert "1 open shift claim left waiting: the approval was refused" in report


def test_the_mail_stub_takes_every_argument_messaging_send_takes():
    """_no_mail swaps the stub in for messaging.send, so a leave notice sent
    straight from the seed (not through on_commit) must still find a stub it
    can call: the leave notifiers pass push_subject."""
    import inspect

    from messaging import services as messaging
    from people.management.commands.seed_demo import _dropped_send
    sent = set(inspect.signature(messaging.send).parameters)
    assert sent <= set(inspect.signature(_dropped_send).parameters)
