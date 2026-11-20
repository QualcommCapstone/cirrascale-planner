"""enrich() fills the derived fields and is safe to repeat."""

from __future__ import annotations

from datetime import datetime

from app.places.enrich import enrich, enrich_all
from app.places.models import Category as C
from tests.factories import place


def test_enrich_fills_every_derived_field():
    raw = place(
        "Pasutakan",
        category=C.EAT,
        source_section="eat",
        subsection="Budget",
        opening_hours="Tue-Sun 11:00-22:00 (closed Mon)",
        price_text="¥1,200",
    )
    done = enrich(raw)
    assert done.opening_hours_osm == "Tu-Su 11:00-22:00"
    assert done.is_open_at(datetime(2026, 11, 17, 12, 0)) is True
    assert (done.price_range, done.price_estimate, done.price_currency) == ("low", 1200.0, "JPY")
    assert done.tags == ["food"] and done.indoor is True
    # the original text and everything else is untouched
    assert done.opening_hours == raw.opening_hours and done.price_text == raw.price_text
    assert done.id == raw.id and done.source_url == raw.source_url


def test_enrich_twice_gives_the_same_result():
    once = enrich(place("Zenpukuji Park", price_text="Free"))
    assert enrich(once) == once


def test_enrich_never_invents_data():
    bare = enrich(place("Ikefukurō"))
    assert bare.opening_hours_osm is None and bare.price_range is None
    assert bare.price_estimate is None and bare.indoor is None and bare.tags == []


def test_old_values_are_recomputed_so_rule_fixes_reach_old_rows():
    stale = place("Zenpukuji Park", tags=["nightlife"], indoor=True, price_range="high")
    fixed = enrich(stale)
    assert (
        fixed.tags == ["nature", "outdoors"] and fixed.indoor is False and fixed.price_range is None
    )


def test_enrich_all_keeps_order():
    names = ["B", "A", "C"]
    assert [p.name for p in enrich_all([place(n) for n in names])] == names
