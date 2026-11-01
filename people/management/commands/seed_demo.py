"""Fictional working data for a staging box.

    manage.py seed_demo --email-base tom@example.org --yes-this-is-staging

Run it last: after hr_sync (and gp_sync, if the GP rota is up) has read the
shared fictional cast from Practice HR. It creates no people. It finds the
cast by the addresses the Practice HR and rota seeds generate, for base
`tom@example.org` Morgan Ellis is `tom+morgan.ellis@example.org`, and then
fills in what a manager would: display settings, hours, days per week and
two years of leave allowances, the nursing and pharmacy team grants, a few
weeks of rota and about nine leave bookings. Everything goes through the
service layer, as the acting manager is the inactive "seed-demo" login, so
every change is in the Activity log. It is one transaction: it all happens or
none of it does.

It is safe to run again: it fills gaps and never overwrites what a manager
has typed, and a second run on the same day changes nothing. A later run adds
the rota weeks that have come into range.

It also writes three open shifts (one with a waiting claim, one filled), two
notices, one message to everyone and one shared sample document, so the
engagement pages are not empty.

It sends NO mail and leaves no trace of any in the Outbox (see `_no_mail`).
Never run it on production: it is the reason for the flag.
"""

import contextlib
from collections import Counter
from dataclasses import dataclass
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from leave.models import BankHoliday, Booking, LeaveType
from leave.services import bookings, years
from leave.services.common import LeaveError
from messaging import services as messaging
from messaging.models import Message, Notice, Outbox
from messaging.services import messages as message_service
from messaging.services import notices as notice_service
from people.models import Department, Person, Team, TeamManager
from people.services import managers, profiles
from shifts.models import Entry, OpenShift, OpenShiftClaim
from shifts.services import entries, open_shifts
from shifts.services import notify as rota_notify
from shifts.services.open_shifts import OpenShiftError
from shifts.services.window import monday
from uploads import services as upload_services
from uploads.models import UploadedFile

ACTOR_EMAIL = "seed-demo@shift-central.invalid"
REQUESTER_EMAIL = "seed-demo-requester@shift-central.invalid"
NOTE = "demo data"
DEFAULT_COLOUR = "#143D5C"          # Person.name_colour's default: a person still on it has never been given one
ROTA_WEEKS = 5                      # this week and the next four
MONDAY_ZERO = date(2000, 1, 3)      # a Monday: the early/late alternation counts weeks from it


@dataclass(frozen=True)
class Member:
    first: str
    last: str
    team: str                       # Practice HR's team name, for the summary only: the database's own is never changed
    title: str
    colour: str
    weekly: Decimal | None = None   # None for a GP: sessions, not hours
    days: int | None = None
    works: tuple = ()               # weekdays on the rota, Monday 0; empty: not on the seeded rota
    shift: str = ""                 # a key of SHIFTS
    dept: str = ""                  # a seeded department's name

    @property
    def gp(self):
        return self.weekly is None

    def email(self, base):
        local, domain = base.split("@")
        return f"{local}+{self.first.lower()}.{self.last.lower()}@{domain}"


D = Decimal
WEEK = (0, 1, 2, 3, 4)
MGMT, RECEP, GPS, NURSE, ADMIN, PHARM, CLEAN = "#143D5C", "#2F6FB3", "#2A7F62", "#B84D6B", "#7A5EB3", "#3A8A8A", "#8C7B6B"

CAST = (
    Member("Morgan", "Ellis", "Management", "Practice Manager", MGMT, D("37.5"), 5),
    Member("Jo", "Whitaker", "Management", "Assistant Practice Manager", MGMT, D("37.5"), 5),
    Member("Dev", "Anand", "Management", "Assistant Practice Manager", MGMT, D("37.5"), 5),
    Member("Rosa", "Delgado", "Reception", "Reception Manager", RECEP, D("37.5"), 5, WEEK, "early", "Reception AG"),
    Member("Sophie", "Brennan", "Reception", "Receptionist", RECEP, D("37.5"), 5, WEEK, "swing", "Reception PMC"),
    Member("Liam", "Doyle", "Reception", "Receptionist", RECEP, D("30"), 4, (0, 1, 2, 3), "swing_back", "Reception AG"),
    Member("Aisha", "Rahman", "Reception", "Receptionist", RECEP, D("22.5"), 3, (0, 2, 4), "late", "Reception PMC"),
    Member("Tomasz", "Kowal", "Reception", "Receptionist", RECEP, D("15"), 2, (1, 3), "early", "Reception PMC"),
    Member("Priya", "Nair", "GPs", "Salaried GP", GPS),
    Member("Callum", "Ross", "GPs", "Salaried GP", GPS),
    Member("Helen", "Okafor", "GPs", "Salaried GP", GPS),
    Member("Fiona", "Marsh", "Nursing", "Lead Nurse", NURSE, D("37.5"), 5, WEEK, "nursing", "Nursing"),
    Member("Grace", "Tanaka", "Nursing", "Practice Nurse", NURSE, D("30"), 4, (0, 1, 2, 3), "nursing", "Nursing"),
    Member("Owen", "Pryce", "Nursing", "Healthcare Assistant", NURSE, D("22.5"), 3, (0, 1, 3), "nursing", "HCA"),
    Member("Elena", "Fischer", "Admin/Secretarial", "Medical Secretary", ADMIN, D("37.5"), 5, WEEK, "office", "Secretarial"),
    Member("Marcus", "Bell", "Admin/Secretarial", "Administrator", ADMIN, D("22.5"), 3, (0, 2, 3), "office", "Workflow"),
    Member("Hamid", "Qureshi", "Pharmacy", "Head Pharmacist", PHARM, D("37.5"), 5, WEEK, "nursing", "Pharmacist"),
    Member("Ines", "Costa", "Pharmacy", "Pharmacy Technician", PHARM, D("30"), 4, (0, 1, 2, 3), "office", "Pharmacy Technician"),
    Member("Doreen", "Hughes", "Cleaning", "Cleaner", CLEAN, D("15"), 5, WEEK, "evening", "Cleaning PMC"),
)

# Every shift nets 7 h 30 min (3 h for the cleaner), the average day of a 37.5 hour,
# five day week: a day of leave costs the same from the rota as from the contract.
EARLY = (time(8, 0), time(16, 15), 45)
LATE = (time(10, 15), time(18, 30), 45)
SHIFTS = {
    "early": lambda week: EARLY,
    "late": lambda week: LATE,
    "swing": lambda week: LATE if week == 0 else EARLY,        # alternating weeks, the opposite of swing_back,
    "swing_back": lambda week: EARLY if week == 0 else LATE,   # so the desk is covered both ends
    "nursing": lambda week: (time(8, 30), time(17, 0), 60),
    "office": lambda week: (time(9, 0), time(17, 15), 45),
    "evening": lambda week: (time(18, 0), time(21, 0), 0),
}

# A full year, five days a week, plus eight bank holidays: the allowance is what a
# weekly figure of hours earns, so a part-timer's is in proportion.
ANNUAL_WEEKS, BANK_HOLIDAY_WEEKS = D("5"), D("1.6")


def _dropped_send(person, subject, body, connection=None, url=None):
    """Stands in for messaging.send: nothing is written or sent."""
    return Outbox(to_person=person, to_email=person.email or "", subject=subject, body=body, error="not sent: seed_demo")


@contextlib.contextmanager
def _no_mail():
    """Nothing is emailed, whatever EMAIL_* is set to, and nothing is queued.

    Booking and approving send mail "after the commit" through
    transaction.on_commit and messaging.send, which writes an Outbox row first.
    Setting EMAIL_HOST="" would send nothing but leave a "mail not configured"
    row for every message, which the Outbox page would show as a failure; the
    locmem backend would leave rows that say "sent". Neither is true to what
    happened here: no message was composed for anyone. So both seams are
    replaced for the length of the run: on_commit takes no callbacks (so none
    waits for the commit, however deep this is called from) and send is a stub
    (so a direct call writes no row either). They are put back afterwards."""
    patched = [(transaction, "on_commit", lambda func, using=None, robust=False: None),
               (messaging, "send", _dropped_send),
               (rota_notify, "send_mail", _dropped_send)]
    real = [getattr(owner, name) for owner, name, _ in patched]
    for owner, name, stub in patched:
        setattr(owner, name, stub)
    try:
        yield
    finally:
        for (owner, name, _), original in zip(patched, real):
            setattr(owner, name, original)


@contextlib.contextmanager
def _requesting_as(person):
    """The login a request is made by: bookings.request is the person's own
    act, so it needs a user whose Person is theirs. A person who has signed in
    has one, and it is used as it is. Otherwise a throwaway inactive login is
    bound to them for the length of the request and deleted; the booking keeps
    no requester then, and the audit line keeps the address it was made as."""
    if person.user_id:
        yield person.user
        return
    user = User.objects.create_user(email=REQUESTER_EMAIL, is_active=False)
    person.user = user
    person.save(update_fields=["user"])
    try:
        yield User.objects.get(pk=user.pk)
    finally:
        Person.objects.filter(pk=person.pk).update(user=None)
        person.user = None
        user.delete()


def _check_base(base):
    if base.count("@") != 1 or "+" in base:
        raise CommandError("--email-base must be local@domain, with exactly one @ and no +")
    local, domain = base.split("@")
    if not local or not domain or any(c.isspace() for c in base):
        raise CommandError("--email-base must be local@domain, with exactly one @ and no +")


def _month_start(day, delta):
    index = day.year * 12 + day.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def _monday_on_or_after(day):
    return day + timedelta(days=(-day.weekday()) % 7)


class Command(BaseCommand):
    help = "Fill a staging Shift Central with fictional working data, after hr_sync has read the fictional cast"

    def add_arguments(self, parser):
        parser.add_argument("--email-base", required=True,
                            help="local@domain: the cast's addresses are local+first.last@domain")
        parser.add_argument("--yes-this-is-staging", action="store_true",
                            help="required: this writes demo data and must never run on production")

    def handle(self, *args, email_base, yes_this_is_staging, **options):
        if not yes_this_is_staging:
            raise CommandError("Refusing to run without --yes-this-is-staging: this writes fictional demo data "
                               "and must never run on production. Nothing was changed.")
        _check_base(email_base)
        people = self._cast_in_database(email_base)
        today = timezone.localdate()
        with _no_mail():
            with transaction.atomic():
                counts = self._seed(people, today)
        self._report(counts)

    # --- preconditions (read only) --------------------------------------

    def _cast_in_database(self, base):
        wanted = {m.email(base).lower(): m for m in CAST}
        rows = list(Person.objects.select_related("team"))
        found, foreign, problems = {}, 0, []
        for person in rows:
            key = (person.email or "").lower()
            if key not in wanted:
                foreign += 1
            elif key in found:
                problems.append("more than one person has the same cast address; the staging database is not what hr_sync makes")
            else:
                found[key] = person
        missing = len(wanted) - len(found)
        if missing:
            problems.append(f"{missing} of the {len(wanted)} people are missing: run hr_sync first (and check --email-base "
                            f"is the one the Practice HR seed used)")
        if foreign:
            problems.append(f"the database holds {foreign} person row{'s' if foreign != 1 else ''} outside the cast: "
                            f"this is for a staging box that holds only the fictional cast")
        if not missing:
            odd = sum(1 for key, m in wanted.items() if found[key].is_gp != m.gp)
            if odd:
                problems.append(f"{odd} of the cast {'is' if odd == 1 else 'are'} not marked as a GP (or marked as one) "
                                f"as the cast expects: check the contracts in Practice HR")
            for name in ("Nursing", "Pharmacy"):
                if not Team.objects.filter(name=name).exists():
                    problems.append(f"there is no {name} team: has hr_sync read the {name.lower()} staff?")
            for what, exists in (("Holiday", LeaveType.objects.filter(seeded=True, draws_from="annual").exists()),
                                 ("Sick leave", LeaveType.objects.filter(seeded=True, sickness=True).exists())):
                if not exists:
                    problems.append(f"the {what} leave type is missing: has migrate been run?")
        if problems:
            raise CommandError("Refusing; nothing was changed.\n  " + "\n  ".join(problems))
        return {m: found[m.email(base).lower()] for m in CAST}

    # --- the work ---------------------------------------------------------

    def _seed(self, people, today):
        since = timezone.now()
        actor = self._actor()
        counts = Counter()
        self._people(actor, people, today, counts)
        self._grants(actor, people, counts)
        plan = self._plan(people, today)
        self._rota(actor, people, today, plan, counts)
        self._leave(actor, people, plan, counts)
        self._engagement(actor, people, today, counts)
        counts["baseline"] = rota_notify.settle_baseline(
            actor, [p for m, p in people.items() if m.works], since,
            "seed_demo: the seeded rota is the starting point")
        return counts

    def _actor(self):
        """The manager the changes are made by: an all-teams manager who cannot
        sign in (inactive, no password, an address that cannot receive mail), so
        that the Activity log says who did it and nobody can become it."""
        user, made = User.objects.get_or_create(email=ACTOR_EMAIL, defaults={"is_active": False, "is_all_teams_manager": True})
        if made:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    def _people(self, actor, people, today, counts):
        for member, person in people.items():
            if not person.job_title:
                colour = member.colour if person.name_colour == DEFAULT_COLOUR else person.name_colour
                counts["display"] += bool(profiles.update_display(actor, person, job_title=member.title, name_colour=colour))
            if member.gp:
                continue
            if person.weekly_hours is None or person.days_per_week is None:
                counts["hours"] += bool(profiles.update_hours(actor, person, person.weekly_hours or member.weekly,
                                                               person.days_per_week or member.days, note=NOTE))
            for year in years.years_for(person, today):
                if not person.allowances.filter(leave_year=year).exists():
                    profiles.set_allowance(actor, person, year, member.weekly * ANNUAL_WEEKS,
                                           member.weekly * BANK_HOLIDAY_WEEKS, note=NOTE)
                    counts["allowances"] += 1

    def _grants(self, actor, people, counts):
        """Fiona Marsh manages Nursing and Hamid Qureshi Pharmacy (setup step 8).
        The four all-teams managers are NOT made here: that is Practice HR's
        "Admin of shift-central" box, applied at each one's sign-in
        (accounts/oidc.py sets User.is_all_teams_manager from the `admin`
        claim and binds the login to the person), so there is nothing to
        seed for them."""
        by_name = {(m.first, m.last): p for m, p in people.items()}
        for who, team_name in ((("Fiona", "Marsh"), "Nursing"), (("Hamid", "Qureshi"), "Pharmacy")):
            person, team = by_name[who], Team.objects.get(name=team_name)
            if not TeamManager.objects.filter(person=person, team=team).exists():
                managers.grant(actor, person, team)
                counts["grants"] += 1

    # --- the plan: dates first, so the rota can cover them -----------------

    def _plan(self, people, today):
        """The bookings, as dates: nothing is written. Left empty when anyone in
        the cast already has a booking (a second run, or a manager's own), so
        a later run on another day does not add a second set."""
        if Booking.objects.filter(person__in=people.values()).exists():
            return []
        bank = set(BankHoliday.objects.values_list("day", flat=True))
        who = {(m.first, m.last): p for m, p in people.items()}
        this = monday(today)

        def free(day):                           # the next working day that is not a bank holiday
            while day.weekday() > 4 or day in bank:
                day += timedelta(days=1)
            return day

        def clear_week(start, length=5):         # the first week from `start` with no bank holiday in it
            for _ in range(12):
                if not any(start + timedelta(days=i) in bank for i in range(length)):
                    return start
                start += timedelta(weeks=1)
            return start

        away = clear_week(_monday_on_or_after(_month_start(today, 1) + timedelta(days=4)))
        away2 = clear_week(away + timedelta(weeks=1))
        ill = clear_week(_monday_on_or_after(_month_start(today, -1) + timedelta(days=7)), 3)
        old = this - timedelta(weeks=6)
        nurse_day = free(this + timedelta(weeks=2, days=1))

        def item(name, first, last, kind, **kw):
            return dict(person=who[name], first=first, last=last, kind=kind, **kw)

        plan = [
            item(("Sophie", "Brennan"), away, away + timedelta(days=4), "book"),
            item(("Liam", "Doyle"), away2, away2 + timedelta(days=4), "book"),
            item(("Grace", "Tanaka"), nurse_day, nurse_day, "book"),
            item(("Elena", "Fischer"), free(this + timedelta(weeks=3, days=4)), free(this + timedelta(weeks=3, days=4)), "book", part="pm"),
            item(("Aisha", "Rahman"), free(this + timedelta(weeks=1, days=4)), free(this + timedelta(weeks=1, days=4)), "request_approved"),
            item(("Ines", "Costa"), free(this + timedelta(weeks=4)), free(this + timedelta(weeks=4, days=1)), "request"),
            item(("Sophie", "Brennan"), ill + timedelta(days=1), ill + timedelta(days=2), "book", sick=True),
            item(("Doreen", "Hughes"), old, old + timedelta(days=1), "book", sick=True, dates_only=True),
            item(("Owen", "Pryce"), free(this + timedelta(weeks=2, days=3)), free(this + timedelta(weeks=2, days=3)), "book", then_cancel=True),
        ]
        # A day outside this leave year and the next cannot be booked (early in January,
        # "last month" is the year before): leave it out here, so its week gets no rota either.
        return [p for p in plan
                if p.get("dates_only") or all(years.year_of(p["person"], d) in years.years_for(p["person"], today)
                                              for d in (p["first"], p["last"]))]

    # --- the rota ----------------------------------------------------------

    def _rota(self, actor, people, today, plan, counts):
        """A shift on each member's own days for this week and the next four,
        and for any week a booking falls in, so that its days are costed from
        the rota and none is left as an "average day" to check. A person's week
        that already has anything in it is left alone."""
        this = monday(today)
        weeks = {this + timedelta(weeks=n) for n in range(ROTA_WEEKS)}
        weeks |= {monday(p["first"]) for p in plan if not p.get("dates_only")}
        bank = set(BankHoliday.objects.values_list("day", flat=True))
        departments = {d.name: d.pk for d in Department.objects.all()}
        for week in sorted(weeks):
            parity = ((week - MONDAY_ZERO).days // 7) % 2
            for member, person in people.items():
                if not member.works or Entry.objects.filter(person=person, day__range=(week, week + timedelta(days=6))).exists():
                    continue
                start, finish, rest = SHIFTS[member.shift](parity)
                for weekday in member.works:
                    day = week + timedelta(days=weekday)
                    if day in bank:
                        continue
                    entries.set_cell(actor, person, day, [{"kind": "shift", "start": start, "finish": finish, "break_minutes": rest,
                                                           "department": departments.get(member.dept)}])
                    counts["entries"] += 1
                counts["person_weeks"] += 1

    # --- leave ---------------------------------------------------------------

    def _leave(self, actor, people, plan, counts):
        holiday = LeaveType.objects.filter(seeded=True, draws_from="annual").order_by("pk").first()
        sick = LeaveType.objects.filter(seeded=True, sickness=True).order_by("pk").first()
        for p in plan:
            person, kind = p["person"], p["kind"]
            leave_type = sick if p.get("sick") else holiday
            part = p.get("part", "whole")
            try:
                with transaction.atomic():
                    if kind == "book":
                        booking = bookings.book(actor, person, leave_type, p["first"], p["last"], part,
                                                note=NOTE, dates_only=p.get("dates_only", False))
                        if p.get("then_cancel"):
                            bookings.cancel(actor, booking, note=NOTE)
                    else:
                        with _requesting_as(person) as user:
                            booking = bookings.request(user, person, leave_type, p["first"], p["last"], part, note=NOTE)
                        if kind == "request_approved":
                            bookings.approve(actor, booking, note=NOTE)
            except LeaveError:
                counts["bookings_skipped"] += 1
                continue
            counts["bookings"] += 1
            booking.refresh_from_db()
            counts[f"bookings_{booking.status}"] += 1

    # --- engagement (spec 5) --------------------------------------------------------

    def _engagement(self, actor, people, today, counts):
        """Open shifts, notices, a message and a shared document, so the new
        pages are not empty. Posts and the one approval go through the service
        layer; the waiting claim is written directly, because claiming needs a
        signed-in login and the cast may not have one yet. No mail: _no_mail
        holds for the whole run."""
        first = max(_monday_on_or_after(today), today + timedelta(days=1))
        by_first = {m.first: p for m, p in people.items()}
        reception = Team.objects.filter(name="Reception").first()
        nursing = Team.objects.filter(name="Nursing").first()
        if reception is None or nursing is None:
            return
        desk = Department.objects.filter(name="Reception AG").first()
        plan = (
            ("demo data: front desk cover", reception, first + timedelta(days=1), time(9), time(13), [reception], desk),
            ("demo data: phones", reception, first + timedelta(days=2), time(14), time(18), [reception], desk),
            ("demo data: clinic support", nursing, first + timedelta(days=3), time(8, 30), time(12, 30), [nursing], None),
        )
        posts = []
        for comment, team, day, start, finish, audience, dept in plan:
            post = OpenShift.objects.filter(comment=comment).first()
            if post is None:
                post = open_shifts.post(actor, team, day, start, finish, 0, dept, comment, False, audience)
                counts["open_shifts"] += 1
            posts.append(post)
        sophie, liam = by_first.get("Sophie"), by_first.get("Liam")
        if sophie is not None and not posts[0].claims.exists():
            OpenShiftClaim.objects.create(open_shift=posts[0], person=sophie, overtime="toil", note="Happy to cover")
        if liam is not None and posts[1].state == OpenShift.State.OPEN and not posts[1].claims.exists():
            claim = OpenShiftClaim.objects.create(open_shift=posts[1], person=liam)
            try:
                open_shifts.approve(actor, claim)
            except OpenShiftError:
                counts["claims_left_waiting"] += 1      # approval refused (leave on the day, say): the claim stays waiting
        if not Notice.objects.filter(title="Fire drill on Thursday").exists():
            notice_service.post(actor, "Fire drill on Thursday", "Meet at the front car park at 10:30. This is a test notice.", True, [], pinned=True)
            counts["notices"] += 1
        if not Notice.objects.filter(title="Car park resurfacing").exists():
            notice_service.post(actor, "Car park resurfacing", "The staff car park is closed next Monday. This is a test notice.", False, [reception.pk])
            counts["notices"] += 1
        if not Message.objects.filter(subject="Welcome to the staging box").exists():
            message_service.send(actor, "Welcome to the staging box", "This is demo data. Nothing here is real.", everyone=True)
            counts["messages"] += 1
        if not UploadedFile.objects.filter(title="Staff handbook (sample)").exists():
            sample = SimpleUploadedFile("staff-handbook-sample.txt", b"Sample handbook. This is demo data.\n")
            upload_services.add(actor, sample, "Staff handbook (sample)", UploadedFile.Kind.SHARED)
            counts["documents"] += 1

    # --- the report ------------------------------------------------------------

    def _report(self, counts):
        out = self.stdout.write
        changed = {k: v for k, v in counts.items() if k not in ("baseline", "person_weeks") and v}
        if not changed:
            out("Nothing to do: the demo data is already in place.")
        else:
            out("Demo data seeded.")
            out(f"  people set up: {counts['display']} display settings, {counts['hours']} sets of hours and days, "
                f"{counts['allowances']} yearly allowances")
            out(f"  team grants: {counts['grants']}")
            out(f"  rota: {counts['entries']} shifts for {counts['person_weeks']} person-weeks")
            out(f"  time off: {counts['bookings']} bookings made "
                f"({counts['bookings_approved']} approved, {counts['bookings_pending']} waiting for a decision, "
                f"{counts['bookings_cancelled']} cancelled), {counts['bookings_skipped']} left out")
            out(f"  engagement: {counts['open_shifts']} open shifts, {counts['notices']} notices, "
                f"{counts['messages']} message, {counts['documents']} document")
            if counts["claims_left_waiting"]:
                n = counts["claims_left_waiting"]
                out(f"  {n} open shift claim{'s' if n != 1 else ''} left waiting: the approval was refused")
        out("All-teams managers: made by Practice HR's 'Admin of shift-central' box when each signs in; "
            "nothing was done for them here.")
        out("No email was sent and none was queued.")
