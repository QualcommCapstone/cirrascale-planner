"""Saving places, loading them back, and the whole ingest pipeline against a real database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.places import repo
from app.places.db import session_scope
from app.places.ingest import ingest
from app.places.models import Category, Place, SourceRef
from tests.factories import WHEN, place, raw

HERE = {"lat": 35.6895, "lng": 139.6917}


def test_a_place_survives_a_round_trip(engine):
    original = place(
        "Pasutakan",
        category=Category.EAT,
        source_section="drink",
        district="Shinjuku",
        address="8F Mylord",
        directions="near the south exit",
        description="Okonomiyaki cooked at your table.",
        opening_hours="11:00-22:00",
        opening_hours_osm="Mo-Su 11:00-22:00",
        price_text="¥1200",
        price_range="low",
        price_estimate=1200.0,
        price_currency="JPY",
        tags=["food", "nightlife"],
        indoor=True,
        website="https://shop.example/pasutakan",
        phone="+81 3-1111-2222",
        wikidata_id="Q123",
        sources=[
            SourceRef(
                source="wikivoyage", url="https://example.org/wikivoyage/Pasutakan", fetched_at=WHEN
            ),
            SourceRef(
                source="osm", url="https://osm.example/node/1", fetched_at=WHEN - timedelta(days=2)
            ),
        ],
        **HERE,
    )
    with session_scope(engine) as session:
        repo.save_places(session, [original])
    with session_scope(engine) as session:
        loaded = repo.get_place(session, original.id)
    assert loaded == original
    assert loaded is not None and loaded.fetched_at.tzinfo is not None


def test_saving_again_updates_instead_of_duplicating(engine):
    p = place("Fire Museum")
    with session_scope(engine) as session:
        assert repo.save_places(session, [p]) == (1, 0)
    with session_scope(engine) as session:
        assert repo.save_places(session, [p.model_copy(update={"description": "New text."})]) == (
            0,
            1,
        )
        assert [x.description for x in repo.search_places(session)] == ["New text."]


def test_search_filters_and_city_match_ignores_case(engine):
    places = [
        place("Fire Museum", **HERE),
        place("Pasta House", category=Category.EAT, source_section="eat"),
        place("Park Hotel", category=Category.SLEEP, source_section="sleep"),
        place("Other Cafe", city="Elsewhere", category=Category.EAT, source_section="eat"),
    ]
    with session_scope(engine) as session:
        repo.save_places(session, places)
        assert len(repo.load_city(session, "testville")) == 3
        assert [
            p.name for p in repo.search_places(session, city="TESTVILLE", category=Category.EAT)
        ] == ["Pasta House"]
        assert [p.name for p in repo.search_places(session, text="hotel")] == ["Park Hotel"]
        assert len(repo.search_places(session, limit=2)) == 2
        assert repo.count_by_city_and_category(session) == [
            ("Elsewhere", "eat", 1),
            ("Testville", "eat", 1),
            ("Testville", "see", 1),
            ("Testville", "sleep", 1),
        ]


# ---- the pipeline -------------------------------------------------------------------


def test_ingest_cleans_dedupes_and_saves(engine):
    listings = [
        raw("Fire Museum", lat=35.6895, lng=139.6917, hours="9-5", price="Free"),
        raw(
            "Fire Museum ",
            source_url="https://en.wikivoyage.org/wiki/Testville/Annex#Fire_Museum",
            lat=35.6896,
            lng=139.6918,
            description="Trucks.",
        ),
        raw("Pasta House", section="eat"),
        raw("x").model_copy(update={"name": "--"}),
    ]
    with session_scope(engine) as session:
        report = ingest(listings, session)
    assert (report.raw, report.cleaned, report.duplicates_removed) == (4, 3, 1)
    assert report.dropped["no usable name"] == 1
    assert (report.inserted, report.updated, report.deleted) == (2, 0, 0)

    with session_scope(engine) as session:
        museum = repo.search_places(session, text="Fire")[0]
    assert museum.opening_hours == "9-5" and museum.description == "Trucks."  # gaps filled
    assert len(museum.sources) == 2


def test_ingesting_twice_changes_nothing(engine):
    listings = [raw("Fire Museum", **HERE), raw("Pasta House", section="eat")]
    with session_scope(engine) as session:
        ingest(listings, session)
    with session_scope(engine) as session:
        before = {p.id for p in repo.search_places(session)}
    with session_scope(engine) as session:
        report = ingest(listings, session)
    with session_scope(engine) as session:
        after = {p.id for p in repo.search_places(session)}
    assert before == after and len(after) == 2
    assert (report.inserted, report.updated, report.duplicates_removed) == (0, 2, 0)


def test_rescrape_updates_text_and_fetch_date(engine):
    with session_scope(engine) as session:
        ingest([raw("Fire Museum", hours="9-5")], session)
    later = WHEN + timedelta(days=30)
    with session_scope(engine) as session:
        ingest([raw("Fire Museum", hours="10-6", fetched_at=later)], session)
    with session_scope(engine) as session:
        (found,) = repo.search_places(session)
    assert found.opening_hours == "10-6"
    assert found.fetched_at == later
    assert len(found.sources) == 1


def test_a_second_source_merges_into_the_existing_place_and_keeps_its_id(engine):
    with session_scope(engine) as session:
        ingest([raw("Fire Museum", **HERE)], session)
        (original,) = repo.search_places(session)

    other = raw(
        "Fire Museum",
        source="osm",
        source_url="https://osm.example/way/9",
        lat=35.6896,
        lng=139.6918,
        hours="Mo-Su 09:30-17:00",
    )
    with session_scope(engine) as session:
        report = ingest([other], session)
    assert report.duplicates_removed == 1

    with session_scope(engine) as session:
        (merged,) = repo.search_places(session)
    assert merged.id == original.id  # ids never change
    assert merged.opening_hours == "Mo-Su 09:30-17:00"
    assert {s.source for s in merged.sources} == {"wikivoyage", "osm"}


def test_existing_rows_that_turn_out_to_be_duplicates_are_cleaned_up(engine):
    a = place("Daigo", source_url="https://x/1", **HERE)
    b = place("Daigo", source_url="https://x/2", lat=35.6896, lng=139.6918)
    with session_scope(engine) as session:
        repo.save_places(session, [a, b])
    with session_scope(engine) as session:
        report = ingest([raw("Another Place", section="eat")], session)
    assert report.deleted == 1
    with session_scope(engine) as session:
        assert sorted(p.name for p in repo.search_places(session)) == ["Another Place", "Daigo"]


def test_unusable_listings_never_reach_the_database(engine):
    bad = [
        raw("Ghost").model_copy(update={"source_url": ""}),
        raw("x").model_copy(update={"name": "!!"}),
    ]
    with session_scope(engine) as session:
        report = ingest(bad, session)
    assert report.cleaned == 0 and report.dropped.total() == 2
    with session_scope(engine) as session:
        assert repo.search_places(session) == []


def test_dry_run_touches_no_database():
    report = ingest(
        [raw("Fire Museum", **HERE), raw("Fire Museum", source_url="https://x/2", **HERE)], None
    )
    assert report.duplicates_removed == 1 and report.saved is False


# ---- the Place model itself -----------------------------------------------------------


def test_a_place_cannot_exist_without_a_source_link():
    values = place("Park").model_dump()
    for bad in ("", "not a link"):
        with pytest.raises(ValidationError):
            Place(**{**values, "source_url": bad})


def test_lat_and_lng_must_come_as_a_pair():
    with pytest.raises(ValidationError):
        place("Park", lat=35.0)


def test_naive_times_are_treated_as_utc():
    p = place("Park", fetched_at=datetime(2026, 1, 1, 12, 0))
    assert p.fetched_at == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


# ---- enrichment through the pipeline -------------------------------------------------


def test_ingest_fills_tags_price_hours_and_indoor(engine):
    listing = raw(
        "Pasutakan",
        section="eat",
        subsection="Budget",
        hours="Tue-Sun 11:00-22:00 (closed Mon)",
        price="¥1,200",
    )
    with session_scope(engine) as session:
        ingest([listing], session)
    with session_scope(engine) as session:
        (found,) = repo.search_places(session)
    assert found.tags == ["food"] and found.indoor is True
    assert (found.price_range, found.price_estimate, found.price_currency) == ("low", 1200.0, "JPY")
    assert found.opening_hours_osm == "Tu-Su 11:00-22:00"
    assert found.is_open_at(datetime(2026, 11, 17, 12, 0)) is True


def test_a_merged_place_is_enriched_from_both_copies(engine):
    a = raw("Zenpukuji Park", **HERE)
    b = raw(
        "Zenpukuji Park",
        source_url="https://en.wikivoyage.org/wiki/Testville/Annex#Z",
        lat=35.6896,
        lng=139.6918,
        hours="Daily 6AM-8PM",
        price="Free",
    )
    with session_scope(engine) as session:
        ingest([a, b], session)
        (found,) = repo.search_places(session)
    assert found.opening_hours_osm == "Mo-Su 06:00-20:00"
    assert found.price_range == "free" and found.indoor is False
