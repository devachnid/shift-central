"""The booking lifecycle (spec section 4): who may do what, covering and
restoring entries, re-costing, refusals, audit and mail."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import transaction

from leave.models import Booking, BookingDay
from leave.services import adjustments, bank_holidays, blackouts, bookings
from leave.services.common import LeaveError
from messaging.models import Outbox
from people.models import AuditEntry
from shifts.models import DayChange, Entry
from shifts.services import entries
from tests.factories import (make_allowance, make_bank_holiday, make_entry, make_person, make_team, make_team_manager,
                             make_type, make_user_for)

pytestmark = pytest.mark.django_db
MON, TUE, WED = date(2027, 3, 1), date(2027, 3, 2), date(2027, 3, 3)
Y27 = date(2027, 1, 1)


@pytest.fixture
def team():
    return make_team("Reception")


@pytest.fixture
def lead(team):
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    return lead


@pytest.fixture
def sam(team):
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    for d in (MON, TUE, WED):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    return sam


def test_staff_request_waits_for_approval_and_mails_the_managers(sam, lead):
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole", note="family")
    assert b.status == "pending" and b.requested_by == sam.user and not BookingDay.objects.exists()
    assert Entry.objects.filter(person=sam, covered_by__isnull=False).count() == 0
    assert sorted(Outbox.objects.values_list("to_person__first_name", flat=True)) == ["Boss", "Lead"]
    assert len(mail.outbox) == 2 and "Sam Patel has requested time off" in mail.outbox[0].subject
    assert AuditEntry.objects.filter(model="leave.booking", object_id=sam.pk).count() == 1


def test_a_request_beyond_the_available_balance_is_refused_but_a_manager_can_book_it(sam, lead):
    adjustments.add(lead.user, sam, Y27, "annual", -(225 * 3600), "test")   # 232.5 h − 225 h leaves 7 h 30 min; two days cost 15 h (LV-24)
    with pytest.raises(LeaveError) as e:
        bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole")
    assert e.value.code == "balance"
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, TUE, "whole")
    assert b.status == "approved" and b.decided_by == lead.user
    from leave.services import balances
    assert balances.statement(sam, Y27).annual_remaining < 0


def test_a_blackout_blocks_a_request_for_its_teams_only(sam, lead, team):
    other = make_team("Nursing")
    blackouts.add(lead.user, MON, WED, [other], "Nursing audit")
    bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    blackouts.add(lead.user, TUE, TUE, [], "everyone")
    with pytest.raises(LeaveError) as e:
        bookings.request(sam.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    assert e.value.code == "blackout"
    assert bookings.book(lead.user, sam, make_type("Holiday"), TUE, TUE, "whole").status == "approved"


def test_only_requestable_types_can_be_requested(sam):
    with pytest.raises(LeaveError) as e:
        bookings.request(sam.user, sam, make_type("Sick leave"), MON, MON, "whole")
    assert e.value.code == "type"


def test_approval_costs_each_day_covers_the_entries_and_writes_day_changes(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole")
    mail.outbox.clear()
    bookings.approve(lead.user, b, "enjoy")
    b.refresh_from_db()
    assert b.status == "approved" and b.manager_note == "enjoy" and b.decided_by == lead.user
    assert list(BookingDay.objects.filter(booking=b).values_list("day", "cost_seconds", "source", "account")) == [
        (MON, 27000, "rota", "annual"), (TUE, 27000, "rota", "annual")]
    assert Entry.objects.filter(person=sam, day__in=(MON, TUE), covered_by__isnull=True).count() == 0
    assert Entry.objects.filter(person=sam, day=WED, covered_by__isnull=True).count() == 1
    assert set(DayChange.objects.filter(person=sam).values_list("day", flat=True)) == {MON, TUE}
    assert mail.outbox[0].to == [sam.email] and "approved" in mail.outbox[0].subject


def test_a_half_day_covers_the_whole_day_but_costs_half(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "am")
    assert BookingDay.objects.get(booking=b).cost_seconds == 13500
    assert Entry.objects.get(person=sam, day=MON).covered_by_id is not None


def test_timed_leave_shortens_the_one_shift_it_falls_in_and_restores_it_on_cancel(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "times", start=time(14, 0), finish=time(15, 30))
    entry = Entry.objects.get(person=sam, day=MON)
    bd = BookingDay.objects.get(booking=b)
    assert (entry.start, entry.finish, entry.covered_by) == (time(9), time(14), None)
    assert (bd.cost_seconds, bd.source, bd.shortened_entry_id, bd.original_start, bd.original_finish) == (5400, "times", entry.pk, time(9), time(17))
    bookings.cancel(lead.user, b, "typo")
    entry.refresh_from_db()
    assert (entry.start, entry.finish) == (time(9), time(17)) and not BookingDay.objects.exists()
    b.refresh_from_db()
    assert b.status == "cancelled"


def test_timed_leave_at_the_start_or_end_keeps_the_other_part(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "times", start=time(9), finish=time(11))
    assert Entry.objects.get(person=sam, day=MON).start == time(11)
    bookings.book(lead.user, sam, make_type("Holiday"), TUE, TUE, "times", start=time(15), finish=time(17))
    assert Entry.objects.get(person=sam, day=TUE).finish == time(15)


def test_overlapping_bookings_are_refused_pending_or_approved(sam, lead):
    bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole")
    with pytest.raises(LeaveError) as e:
        bookings.book(lead.user, sam, make_type("Training"), TUE, WED, "whole")
    assert e.value.code == "overlap"


def test_managers_never_approve_their_own_and_the_flag_books_own_leave_straight_away(lead, team):
    make_allowance(lead, Y27, 100, 30)
    make_entry(lead, MON, start=time(9), finish=time(17))
    assert not bookings.may_book(lead.user, lead)
    b = bookings.request(lead.user, lead, make_type("Holiday"), MON, MON, "whole")
    assert not bookings.may_decide(lead.user, b)
    with pytest.raises(PermissionDenied):
        bookings.approve(lead.user, b)
    lead.own_leave_without_approval = True
    lead.save()
    assert bookings.may_book(lead.user, lead)
    make_entry(lead, TUE, start=time(9), finish=time(17))
    b2 = bookings.book(lead.user, lead, make_type("Holiday"), TUE, TUE, "whole", costs={TUE: 3600})
    assert b2.status == "approved"
    bd = BookingDay.objects.get(booking=b2)
    assert (bd.cost_seconds, bd.source) == (8 * 3600, "rota")      # a self-booker's typed costs are ignored


def test_a_team_manager_cannot_book_for_another_team(sam, lead):
    other = make_person(first_name="Nur", team=make_team("Nursing"))
    with pytest.raises(PermissionDenied):
        bookings.book(lead.user, other, make_type("Holiday"), MON, MON, "whole")


def test_cancellation_is_requested_by_staff_and_decided_by_a_manager(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, TUE, "whole")
    mail.outbox.clear()
    bookings.request_cancel(sam.user, b, "plans changed")
    b.refresh_from_db()
    assert b.status == "cancel_requested" and BookingDay.objects.filter(booking=b).count() == 2    # still costs until decided
    assert mail.outbox[0].to == [lead.email]
    bookings.decide_cancel(lead.user, b, approve=False, note="too late")
    b.refresh_from_db()
    assert b.status == "approved"
    bookings.request_cancel(sam.user, b)
    bookings.decide_cancel(lead.user, b, approve=True)
    b.refresh_from_db()
    assert b.status == "cancelled" and not BookingDay.objects.exists()
    assert Entry.objects.filter(person=sam, covered_by__isnull=False).count() == 0
    past = bookings.book(lead.user, sam, make_type("Holiday"), date(2026, 3, 2), date(2026, 3, 2), "whole")    # before today, in this leave year
    with pytest.raises(LeaveError) as e:
        bookings.request_cancel(sam.user, past)
    assert e.value.code == "dates"      # staff cannot cancel a past booking


def test_edit_recosts_as_undo_and_reapply(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.edit(lead.user, b, last=TUE, description="Spring break")
    b.refresh_from_db()
    assert (b.first_day, b.last_day, b.label) == (MON, TUE, "Spring break")
    assert BookingDay.objects.filter(booking=b).count() == 2
    assert Entry.objects.filter(person=sam, day__in=(MON, TUE), covered_by__isnull=False).count() == 2
    row = AuditEntry.objects.filter(model="leave.booking", object_id=sam.pk).latest("pk")
    assert "Spring break" in row.after and "Holiday" in row.before


def test_an_override_is_logged_and_never_recosted(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bd = BookingDay.objects.get(booking=b)
    bookings.override_day(lead.user, bd, 4 * 3600, "half pay day")
    bd.refresh_from_db()
    assert (bd.cost_seconds, bd.source, bd.override_note, bd.override_by) == (14400, "override", "half pay day", lead.user)
    assert not bookings.recost(bd)
    with pytest.raises(ValueError):
        bookings.override_day(lead.user, bd, 3600, "")


def test_recost_follows_the_rota_for_a_whole_day_and_flags_managers(sam, lead):
    aug = date(2027, 8, 11)
    b = bookings.book(lead.user, sam, make_type("Holiday"), aug, aug, "whole")
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.source, bd.placeholder) == (27000, "placeholder", True)
    mail.outbox.clear()
    make_entry(sam, aug, start=time(8), finish=time(16, 15), break_minutes=60)
    assert bookings.after_rota_write(sam, aug) == []
    bd.refresh_from_db()
    assert (bd.cost_seconds, bd.source, bd.placeholder) == (26100, "rota", False)
    assert Entry.objects.get(person=sam, day=aug).covered_by == bd
    assert mail.outbox and "cost to check" in mail.outbox[0].subject.lower()


def test_adjustments_need_a_reason_and_are_audited(sam, lead):
    row = adjustments.add(lead.user, sam, Y27, "annual", 15 * 3600, "carried over from FindMyShift 2026")
    assert row.seconds == 54000 and AuditEntry.objects.filter(model="leave.adjustment", object_id=sam.pk).exists()
    with pytest.raises(ValueError):
        adjustments.add(lead.user, sam, Y27, "annual", 3600, " ")
    with pytest.raises(PermissionDenied):
        adjustments.add(sam.user, sam, Y27, "annual", 3600, "me")


def test_bank_holidays_are_booked_with_typed_hours_for_many_people(sam, lead, team):
    make_bank_holiday(date(2027, 5, 3), "Early May bank holiday")
    nina = make_person(first_name="Nina", team=team)
    booked, skipped = bank_holidays.book_many(lead.user, date(2027, 5, 3), {sam.pk: 27000, nina.pk: 0})
    assert (booked, skipped) == (2, 0)
    bd = BookingDay.objects.get(booking__person=sam, day=date(2027, 5, 3))
    assert (bd.cost_seconds, bd.account, bd.source, bd.override_note) == (27000, "bank_holiday", "override", "bank holiday")
    assert bank_holidays.book_many(lead.user, date(2027, 5, 3), {sam.pk: 27000}) == (0, 1)


def test_describe_is_the_audit_line():
    from leave.services.common import describe
    sam = make_person()
    b = Booking(person=sam, type=make_type("Holiday"), first_day=MON, last_day=TUE, status="approved")
    assert describe(b, 45000) == "Holiday 1–2 Mar 2027, whole days, 12 h 30 min, approved"


# --- stale instances, mail after commit, grid rewrites, edits that keep overrides -------------

def test_a_stale_instance_cannot_decide_a_request_twice(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole")
    stale = Booking.objects.get(pk=b.pk)
    bookings.approve(lead.user, b)
    with pytest.raises(LeaveError) as e:
        bookings.decline(lead.user, stale)
    assert e.value.code == "status"
    with pytest.raises(LeaveError):
        bookings.approve(lead.user, stale)
    assert Booking.objects.get(pk=b.pk).status == "approved" and BookingDay.objects.filter(booking=b).count() == 2
    stale = Booking.objects.get(pk=b.pk)
    bookings.cancel(lead.user, b)
    with pytest.raises(LeaveError) as e:
        bookings.decide_cancel(lead.user, stale, approve=True)
    assert e.value.code == "status" and Booking.objects.get(pk=b.pk).status == "cancelled"


def test_the_instance_the_caller_holds_is_brought_up_to_date(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, TUE, "whole")
    bookings.approve(lead.user, b, "enjoy")
    assert (b.status, b.manager_note, b.decided_by) == ("approved", "enjoy", lead.user)


def test_mail_from_a_re_cost_waits_for_the_outermost_commit(sam, lead, django_capture_on_commit_callbacks):
    aug = date(2027, 8, 11)
    bookings.book(lead.user, sam, make_type("Holiday"), aug, aug, "whole")
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        with transaction.atomic():
            make_entry(sam, aug, start=time(8), finish=time(16, 15), break_minutes=60)
            bookings.after_rota_write(sam, aug)
            assert len(mail.outbox) == 0
        assert len(mail.outbox) == 0
    assert len(callbacks) == 1 and len(mail.outbox) == 1 and "cost to check" in mail.outbox[0].subject.lower()


def test_a_rolled_back_booking_sends_no_mail(sam, lead, django_capture_on_commit_callbacks):
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        try:
            with transaction.atomic():
                bookings.book(lead.user, sam, make_type("Holiday"), date(2027, 8, 11), date(2027, 8, 11), "whole")
                raise RuntimeError("roll back")
        except RuntimeError:
            pass
    assert mail.outbox == []


def test_a_grid_rewrite_of_a_timed_day_keeps_the_leave_restorable(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "times", start=time(14, 0), finish=time(15, 30))
    entries.set_cell_text(lead.user, sam, MON, "09:00-14:00")      # deletes and recreates the day's rows
    bd = BookingDay.objects.get(booking=b)
    assert bd.shortened_entry_id is None
    assert bookings.after_rota_write(sam, MON) == [Entry.objects.get(person=sam, day=MON).pk]
    bd.refresh_from_db()
    entry = Entry.objects.get(person=sam, day=MON)
    assert bd.shortened_entry_id == entry.pk
    bookings.cancel(lead.user, b)
    entry.refresh_from_db()
    assert (entry.start, entry.finish) == (time(9), time(17))


def test_a_grid_rewrite_of_a_day_the_leave_filled_covers_the_new_shift(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "times", start=time(9), finish=time(17))
    assert Entry.objects.get(person=sam, day=MON).covered_by is not None
    entries.set_cell_text(lead.user, sam, MON, "09:00-17:00 1 hour break")
    assert Entry.objects.get(person=sam, day=MON).covered_by is None
    assert bookings.after_rota_write(sam, MON) == []
    assert Entry.objects.get(person=sam, day=MON).covered_by == BookingDay.objects.get(booking=b)


def test_editing_the_label_of_a_bank_holiday_keeps_its_typed_cost(sam, lead):
    make_bank_holiday(date(2027, 5, 3), "Early May bank holiday")
    b = bank_holidays.book(lead.user, sam, date(2027, 5, 3), 27000)
    bookings.edit(lead.user, b, description="Early May")
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.source, bd.override_note) == (27000, "override", "bank holiday")
    b.refresh_from_db()
    assert b.label == "Early May"


def test_extending_a_booking_keeps_the_overrides_on_the_days_it_already_had(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.override_day(lead.user, BookingDay.objects.get(booking=b), 4 * 3600, "half pay day")
    bookings.edit(lead.user, b, last=TUE)
    first, second = BookingDay.objects.filter(booking=b)
    assert (first.day, first.cost_seconds, first.source, first.override_note, first.override_by) == (MON, 14400, "override", "half pay day", lead.user)
    assert (second.day, second.cost_seconds, second.source) == (TUE, 27000, "rota")
    assert Entry.objects.filter(person=sam, day__in=(MON, TUE), covered_by__isnull=False).count() == 2
