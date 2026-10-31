"""Covered entries vanish from every read of the rota; writes on a covered
day re-cost it; the window payload carries the leave tile."""

import csv
import io
from datetime import date, time
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import BookingDay
from leave.services import bookings
from shifts.models import Entry
from shifts.services import entries, hours, today, window
from tests import clock
from tests.factories import (make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for)

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]    # set on the 2026-27 calendar
MON, TUE = date(2027, 3, 1), date(2027, 3, 2)
Y27 = date(2027, 1, 1)


@pytest.fixture
def lead():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    return lead


@pytest.fixture
def sam(lead):
    sam = make_person(first_name="Sam", team=lead.team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    make_entry(sam, MON, start=time(9), finish=time(17), break_minutes=30)
    make_entry(sam, TUE, start=time(9), finish=time(17), break_minutes=30)
    return sam


def _row(payload, person):
    return next(r for r in payload["rows"] if r["person"] == person.pk)


def test_the_window_hides_covered_entries_and_carries_the_leave(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole", description="Spring")
    p = window.payload(lead.user, MON, 1, {})
    row = _row(p, sam)
    assert MON.isoformat() not in row["cells"] and TUE.isoformat() in row["cells"]
    leave = row["leave"][MON.isoformat()]
    assert leave["type"] == "Holiday" and leave["label"] == "Spring" and leave["part"] == "whole" and leave["status"] == "approved"
    assert leave["cost"] == 27000 and "paid" in leave
    nina = make_person(first_name="Nina", team=lead.team)
    make_user_for(nina)
    theirs = _row(window.payload(nina.user, MON, 1, {}), sam)["leave"][MON.isoformat()]
    assert theirs["label"] == "Holiday" and "description" not in theirs and "cost" not in theirs and "paid" not in theirs


def test_pending_requests_show_hatched_with_the_type(sam, lead):
    bookings.request(sam.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    leave = _row(window.payload(lead.user, MON, 1, {}), sam)["leave"][TUE.isoformat()]
    assert leave["status"] == "pending" and leave["type"] == "Holiday"
    assert TUE.isoformat() in _row(window.payload(lead.user, MON, 1, {}), sam)["cells"]    # pending covers nothing


def test_a_write_on_a_covered_day_recosts_and_answers_only_the_visible_rows(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    rows = entries.set_cell_text(lead.user, sam, MON, "08:00-16:15 1 hour break")
    assert rows == []
    bd = BookingDay.objects.get(booking=b)
    assert bd.cost_seconds == 26100 and Entry.objects.get(person=sam, day=MON).covered_by == bd


def test_move_and_paste_skip_covered_target_days(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    result = entries.paste(lead.user, (sam.pk, MON), {"days": 2, "rows": [[[{"kind": "comment", "text": "x"}], [{"kind": "comment", "text": "y"}]]]}, "replace", [sam.pk])
    assert result.skipped == 1 and Entry.objects.filter(person=sam, day=TUE, covered_by__isnull=True).count() == 0
    result = entries.move(lead.user, [(sam.pk, MON)], 1, 0, True, [sam.pk])
    assert result.skipped == 1


def test_hours_report_and_today_leave_covered_entries_out(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    blocks, _, _ = hours.report(lead.user, MON, TUE)
    sam_block = next(b for b in blocks if b["person"] == sam)
    assert sam_block["total"].total_seconds() == 27000      # Tuesday only
    board = today.board(MON)
    assert sam.pk not in {p["person"].pk for s in board["sites"] for t in s["teams"] for p in t["people"]}
    assert board["off"] == [{"person": sam, "label": "Holiday"}]


def test_the_download_and_phone_list_show_the_leave(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "am")
    c = Client()
    c.force_login(lead.user)
    text = c.get(f"/rota/download/?from={MON}").content.decode()
    row = next(r for r in csv.reader(io.StringIO(text)) if r[0] == "Sam Patel")
    assert row[2] == "Holiday (morning)" and row[3].startswith("09:00-17:00")
    body = c.get(f"/rota/?from={MON}").content.decode()
    assert "tile-leave" in body and "Holiday" in body


def test_the_shift_dialog_on_a_covered_day_shows_the_form_with_the_leave_note(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = Client()
    c.force_login(lead.user)
    body = c.get(f"/rota/shift/{sam.pk}/{MON}/").content.decode()
    assert "Sam Patel is off this day (Holiday). The shift you set here is what they would have worked" in body
    assert "stays hidden on the grid" in body
    assert f"/time-off/{b.pk}/" in body and 'name="start"' in body
    assert 'value="09:00"' in body       # prefilled from the covered shift
    assert f"/rota/shift/{sam.pk}/{MON}/{Entry.objects.get(person=sam, day=MON).pk}/" in body


def test_setting_the_shift_behind_a_placeholder_day_re_costs_it(sam, lead):
    from messaging.models import Outbox
    week = date(2027, 3, 15)           # a week with no rota: costed on the average day (7 h 30 min)
    bookings.book(lead.user, sam, make_type("Holiday"), week, week, "whole")
    bd = BookingDay.objects.get(booking__person=sam, day=week)
    assert bd.placeholder and bd.cost_seconds == 27000
    c = Client()
    c.force_login(lead.user)
    assert 'name="start"' in c.get(f"/rota/shift/{sam.pk}/{week}/").content.decode()
    r = c.post(f"/rota/shift/{sam.pk}/{week}/", {"start": "08:00", "finish": "16:00", "break_minutes": "0", "overtime": ""})
    assert r.json() == {"refresh": True}
    bd.refresh_from_db()
    assert (bd.source, bd.placeholder, bd.cost_seconds) == ("rota", False, 8 * 3600)
    shift = Entry.objects.get(person=sam, day=week)
    assert shift.covered_by_id == bd.pk                       # hidden on the grid, behind the leave
    assert "Leave cost to check" in " ".join(Outbox.objects.values_list("subject", flat=True))


def test_editing_the_shift_behind_leave_replaces_it_and_keeps_it_covered(sam, lead):
    bd_booking = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = Client()
    c.force_login(lead.user)
    r = c.post(f"/rota/shift/{sam.pk}/{MON}/", {"start": "10:00", "finish": "16:00", "break_minutes": "0", "overtime": ""})
    assert r.json() == {"refresh": True}
    rows = Entry.objects.filter(person=sam, day=MON)
    assert rows.count() == 1 and rows.first().start == time(10) and rows.first().covered_by is not None
    assert BookingDay.objects.get(booking=bd_booking).cost_seconds == 6 * 3600


def test_only_a_manager_can_set_the_shift_behind_leave(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = Client()
    c.force_login(sam.user)
    assert c.get(f"/rota/shift/{sam.pk}/{MON}/").status_code == 403
    assert c.post(f"/rota/shift/{sam.pk}/{MON}/", {"start": "08:00", "finish": "16:00", "break_minutes": "0"}).status_code == 403
    admin = make_team("Admin")
    other = make_person(first_name="Other", team=admin)
    make_user_for(other)
    make_team_manager(other, admin)             # a manager, but not Sam's
    c2 = Client()
    c2.force_login(other.user)
    assert c2.get(f"/rota/shift/{sam.pk}/{MON}/").status_code == 403


def test_the_note_on_a_part_day_says_the_cost_is_not_changed(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "am")
    c = Client()
    c.force_login(lead.user)
    body = c.get(f"/rota/shift/{sam.pk}/{MON}/").content.decode()
    assert "does not change what this leave costs" in body and 'name="start"' in body


def test_clear_and_cut_never_touch_a_covered_source_day(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    result = entries.clear(lead.user, [(sam.pk, MON)])
    assert result.skipped == 1 and result.cells == {}
    covered = Entry.objects.get(person=sam, day=MON)
    assert covered.covered_by is not None
    bookings.cancel(lead.user, b)
    covered.refresh_from_db()
    assert covered.covered_by is None and (covered.start, covered.finish) == (time(9), time(17))


def test_a_cut_move_of_a_covered_day_leaves_both_days_alone(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    result = entries.move(lead.user, [(sam.pk, MON)], 1, 0, False, [sam.pk])
    assert result.skipped == 1
    assert Entry.objects.get(person=sam, day=MON).covered_by is not None
    tue = Entry.objects.get(person=sam, day=TUE)
    assert tue.covered_by is None and (tue.start, tue.finish) == (time(9), time(17))


def test_find_and_replace_skips_a_day_off(sam, lead):
    """S19: as clear and move do; the shift behind leave is set from its dialog."""
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    result = entries.replace(lead.user, [(sam.pk, MON), (sam.pk, TUE)], "17:00", "16:00", False)
    assert result.skipped == 1
    mon, tue = Entry.objects.get(person=sam, day=MON), Entry.objects.get(person=sam, day=TUE)
    assert mon.finish == time(17) and mon.covered_by is not None
    assert tue.finish == time(16)


def test_a_blank_typed_cell_on_a_covered_day_cannot_delete_the_hidden_shift(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    assert entries.set_cell_text(lead.user, sam, MON, "") == []
    assert Entry.objects.get(person=sam, day=MON).covered_by is not None


# --- a timed booking and the shift set after it (S2, S3)

def _timed(sam, lead, day):
    return bookings.book(lead.user, sam, make_type("Holiday"), day, day, "times", start=time(14), finish=time(15, 30))


def test_a_shift_set_after_timed_leave_in_an_empty_week_is_shortened_not_covered(sam, lead):
    week = date(2027, 3, 15)
    b = _timed(sam, lead, week)
    entries.set_cell(lead.user, sam, week, [{"kind": "shift", "start": "09:00", "finish": "17:00", "break_minutes": 30}])
    shift = Entry.objects.get(person=sam, day=week)
    assert shift.covered_by_id is None and (shift.start, shift.finish) == (time(9), time(14))
    bd = BookingDay.objects.get(booking=b)
    assert bd.shortened_entry_id == shift.pk and (bd.original_start, bd.original_finish) == (time(9), time(17))
    bookings.cancel(lead.user, b, "")
    shift.refresh_from_db()
    assert (shift.start, shift.finish) == (time(9), time(17)), "cancelling gives the shift back whole"


def test_a_shift_that_is_the_timed_leave_is_covered_when_set_after_it(sam, lead):
    week = date(2027, 3, 15)
    b = _timed(sam, lead, week)
    entries.set_cell(lead.user, sam, week, [{"kind": "shift", "start": "14:00", "finish": "15:30"}])
    assert Entry.objects.get(person=sam, day=week).covered_by_id == BookingDay.objects.get(booking=b).pk


def test_the_shift_dialog_on_a_timed_day_edits_the_shortened_shift(sam, lead):
    b = _timed(sam, lead, MON)               # Sam's 09:00-17:00 is shortened to 09:00-14:00
    shortened = Entry.objects.get(person=sam, day=MON)
    c = Client()
    c.force_login(lead.user)
    body = c.get(f"/rota/shift/{sam.pk}/{MON}/").content.decode()
    assert "Sam Patel has timed leave 14:00–15:30 this day. The shift you set here is shortened around it on the grid." in body
    assert "stays hidden" not in body
    assert 'value="09:00"' in body and 'value="14:00"' in body and "Update shift" in body
    assert f"/rota/shift/{sam.pk}/{MON}/{shortened.pk}/" in body
    r = c.post(f"/rota/shift/{sam.pk}/{MON}/", {"start": "08:00", "finish": "17:00", "break_minutes": "30", "overtime": ""})
    assert r.json() == {"refresh": True}
    rows = list(Entry.objects.filter(person=sam, day=MON))
    assert len(rows) == 1, "the shift is edited, not a second one added"
    assert (rows[0].start, rows[0].finish, rows[0].covered_by_id) == (time(8), time(14), None)
    bd = BookingDay.objects.get(booking=b)
    assert bd.shortened_entry_id == rows[0].pk and (bd.original_start, bd.original_finish) == (time(8), time(17))


def test_saving_the_shortened_shift_unchanged_keeps_its_original_times(sam, lead):
    b = _timed(sam, lead, MON)
    c = Client()
    c.force_login(lead.user)
    c.post(f"/rota/shift/{sam.pk}/{MON}/", {"start": "09:00", "finish": "14:00", "break_minutes": "30", "overtime": "", "text": "x"})
    row = Entry.objects.get(person=sam, day=MON)
    assert (row.start, row.finish) == (time(9), time(14))
    bd = BookingDay.objects.get(booking=b)
    assert bd.shortened_entry_id == row.pk and (bd.original_start, bd.original_finish) == (time(9), time(17))


def test_the_shift_dialog_on_a_timed_day_with_no_shift_adds_one(sam, lead):
    week = date(2027, 3, 15)
    _timed(sam, lead, week)
    c = Client()
    c.force_login(lead.user)
    body = c.get(f"/rota/shift/{sam.pk}/{week}/").content.decode()
    assert "has timed leave 14:00–15:30 this day" in body and "Add shift" in body
