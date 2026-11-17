"""Opening-hours text -> OpenStreetMap format. The rule: understand fully, or say nothing."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.places.hours import parse_hours
from tests.factories import place

# Real examples from the Tokyo and Sedona pages.
UNDERSTOOD = [
    ("10:00-21:00", "Mo-Su 10:00-21:00"),
    ("Daily 10:00-23:00", "Mo-Su 10:00-23:00"),
    ("7 AM–7 PM everyday", "Mo-Su 07:00-19:00"),
    ("Daily 6AM-11PM", "Mo-Su 06:00-23:00"),
    ("Tue-Sun 10:00-17:00 (closed Mon)", "Tu-Su 10:00-17:00"),
    ("Wed-Sun 08:30-18:00", "We-Su 08:30-18:00"),
    (
        "Closed Mon; Tue Thu-Sun 11:00-17:00, Wed 11:00-20:00",
        "Tu,Th-Su 11:00-17:00; We 11:00-20:00",
    ),
    ("Wed–Mon 10:00–22:00, Tue 10:00–17:00", "Mo,We-Su 10:00-22:00; Tu 10:00-17:00"),
    ("Sun-Thu 6:30AM-5PM, Fri Sat 6:30AM-6PM", "Mo-Th,Su 06:30-17:00; Fr,Sa 06:30-18:00"),
    ("17:00-03:00", "Mo-Su 17:00-03:00"),
    ("18:00–05:00 daily", "Mo-Su 18:00-05:00"),
    ("Daily 10AM-2AM", "Mo-Su 10:00-02:00"),
    ("24 hours daily", "24/7"),
    ("Mon-Fri 10:00-18:00, closed weekends and holidays", "Mo-Fr 10:00-18:00"),
    ("11:30-14:00, 17:00-22:00", "Mo-Su 11:30-14:00,17:00-22:00"),
    ("17:00-21:00 on Fri, Sat", "Fr,Sa 17:00-21:00"),
    ("3-6PM", "Mo-Su 15:00-18:00"),
    # notes that don't change the hours
    ("11:00-22:30 (last order 22:00)", "Mo-Su 11:00-22:30"),
    ("Tue-Sun 09:30-17:00 (last entry 16:00)", "Tu-Su 09:30-17:00"),
    # already in OpenStreetMap format (what the OSM source will give us)
    (
        "Mo-Fr 09:00-17:00; Sa 10:00-14:00; PH off",
        "Mo-Fr 09:00-17:00; Sa 10:00-14:00",
    ),  # PH rule dropped
]

# Things we must NOT turn into hours: a wrong "open" is worse than "unknown".
NOT_UNDERSTOOD = [
    "Closed Sundays",  # no opening times at all
    "Closed Tue and third Mon of the month",
    "Daily 10:00-17:00 (until 19:00 on Fridays)",  # an exception we can't apply
    "Daily 11:00-21:00 (Sun until 19:30)",
    "Sun-Thu 11AM-10PM, Fri Sat 11AM-11PM; daily Happy Hour 3-6PM",
    "Every year at the end of August 17:00-21:00 on Fri, Sat, Sun",
    "Sep 1-Apr 30: 09:00-16:30, May 1-Aug 31: 09:00-17:00; closed Mondays",
    "Mon-Thu 10:00-20:00, Fri Sat 10:00-21:00, Sun holiday 10:00-20:00",
    "Sun-Thu 19:00-00:00, Fri Sat all night",
    "17:30-12:00; closed Sundays and holidays",  # 18.5 h overnight: surely a typo
    "10-5",  # 10 to 5 what?
    "Many of the shops are not open until late morning or early afternoon",
    "Mon-Fri 9:00-17:00, Mon-Sat 10:00-12:00",  # Monday described twice
    "10:00-10:00",
    "25:00-26:00",
    "sunrise to sunset",
    "",
]


@pytest.mark.parametrize(("text", "expected"), UNDERSTOOD)
def test_understood_hours(text, expected):
    assert parse_hours(text) == expected


@pytest.mark.parametrize("text", NOT_UNDERSTOOD)
def test_unclear_hours_are_left_alone(text):
    assert parse_hours(text) is None


def test_none_in_none_out():
    assert parse_hours(None) is None


def test_result_answers_is_it_open():
    museum = place("Museum", opening_hours_osm=parse_hours("Tue-Sun 10:00-17:00 (closed Mon)"))
    assert museum.is_open_at(datetime(2026, 11, 17, 12, 0)) is True  # Tuesday noon
    assert museum.is_open_at(datetime(2026, 11, 17, 18, 0)) is False  # Tuesday 6 pm
    assert museum.is_open_at(datetime(2026, 11, 16, 12, 0)) is False  # Monday noon


def test_overnight_hours_work_after_midnight():
    bar = place("Bar", opening_hours_osm=parse_hours("17:00-03:00"))
    assert bar.is_open_at(datetime(2026, 11, 17, 2, 0)) is True
    assert bar.is_open_at(datetime(2026, 11, 17, 10, 0)) is False


def test_unknown_hours_answer_none():
    assert place("Park").is_open_at(datetime(2026, 11, 17, 12, 0)) is None
