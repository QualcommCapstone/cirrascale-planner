"""Price text -> level and rough cost."""

from __future__ import annotations

import pytest

from app.places.models import Category as C
from app.places.price import Price, parse_price

CASES = [
    # text, category, heading, expected (level, estimate, currency)
    ("Free", C.SEE, None, ("free", 0.0, None)),
    ("free", C.SEE, "Museums", ("free", 0.0, None)),
    ("Free; donations appreciated", C.SEE, None, ("free", 0.0, None)),
    ("Free (increasing to ¥1000 on 1 November 2025)", C.SEE, None, ("free", 0.0, None)),
    ("¥300", C.SEE, None, ("low", 300.0, "JPY")),
    ("¥2,000-3,000", C.EAT, None, ("mid", 2500.0, "JPY")),
    ("¥980-1800", C.EAT, None, ("low", 1390.0, "JPY")),
    ("$10 or less", C.EAT, None, ("low", 10.0, "USD")),
    ("from 1000¥", C.EAT, None, ("low", 1000.0, "JPY")),
    ("Lunch ¥10,000, dinner ¥20,000-25,000 per person", C.EAT, None, ("high", 10000.0, "JPY")),
    ("$239/night", C.SLEEP, None, ("high", 239.0, "USD")),
    ("¥7000", C.SLEEP, None, ("low", 7000.0, "JPY")),
    ("€45", C.SLEEP, None, ("low", 45.0, "EUR")),
    ("£300 per night", C.SLEEP, None, ("high", 300.0, "GBP")),
    ("Adults ¥1,800; Kids over 4 years old ¥600", C.DO, None, ("low", 1800.0, "JPY")),
    ("Adults ¥5,000", C.DO, None, ("mid", 5000.0, "JPY")),
    ("¥700 adult (16-64), ¥350 senior, free under 12", C.SEE, None, ("low", 700.0, "JPY")),
]


@pytest.mark.parametrize(("text", "category", "heading", "expected"), CASES)
def test_price_parsing(text, category, heading, expected):
    assert parse_price(text, category=category, subsection=heading) == Price(*expected)


@pytest.mark.parametrize(
    ("heading", "level"), [("Budget", "low"), ("Mid-range", "mid"), ("Splurge", "high")]
)
def test_wikivoyage_heading_beats_the_amount(heading, level):
    # ¥2,000 alone would be "mid"; the editors' heading is the better judge of local prices.
    assert parse_price("¥2,000", category=C.EAT, subsection=heading).level == level
    assert parse_price("¥2,000", category=C.SLEEP, subsection=heading).level == level


def test_heading_alone_gives_a_level_even_without_a_price():
    assert parse_price(None, category=C.EAT, subsection="Splurge") == Price("high")
    assert parse_price("varies", category=C.SLEEP, subsection="Budget") == Price("low")


def test_headings_do_not_apply_to_sights():
    assert parse_price("¥300", category=C.SEE, subsection="Budget").level == "low"
    assert parse_price(None, category=C.SEE, subsection="Splurge") == Price(None)


@pytest.mark.parametrize("text", [None, "", "varies", "ask at the door", "x" * 300 + " ¥5"])
def test_unknown_prices_stay_unknown(text):
    assert parse_price(text, category=C.SEE) == Price(None)


def test_unknown_currency_gives_amount_but_no_level():
    result = parse_price("500 rupees", category=C.EAT)
    assert result.level is None
