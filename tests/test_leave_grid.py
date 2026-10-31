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
from tests.factories import (make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for)

pytestmark = pytest.mark.django_db
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


def test_the_shift_dialog_on_a_covered_day_shows_the_leave_instead_of_the_form(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = Client()
    c.force_login(lead.user)
    body = c.get(f"/rota/shift/{sam.pk}/{MON}/").content.decode()
    assert "Holiday" in body and f"/time-off/{b.pk}/" in body and 'name="start"' not in body


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


def test_a_blank_typed_cell_on_a_covered_day_cannot_delete_the_hidden_shift(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    assert entries.set_cell_text(lead.user, sam, MON, "") == []
    assert Entry.objects.get(person=sam, day=MON).covered_by is not None
