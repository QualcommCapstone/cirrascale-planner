"""Duplicate detection and merging. Wrongly merging two real places is the worst outcome,
so most of these tests check that places stay APART."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.places.dedupe import (
    REASON_CORROBORATED,
    REASON_NEAR,
    REASON_SAME_ID,
    REASON_WIKIDATA,
    dedupe,
    normalize_name,
)
from app.places.models import Category
from tests.factories import WHEN, place

HERE = {"lat": 35.6895, "lng": 139.6917}
NEARBY = {"lat": 35.6896, "lng": 139.6918}  # about 14 m away
FAR = {"lat": 35.7295, "lng": 139.7317}  # several km away


def names(result):
    return [p.name for p in result.places]


# ---- should merge ------------------------------------------------------------------


def test_same_name_and_nearly_same_spot_merge():
    result = dedupe([place("Daigo", **HERE), place("Daigo", source_url="https://x/2", **NEARBY)])
    assert names(result) == ["Daigo"]
    assert result.duplicates_removed == 1
    assert result.merges[0].reason == REASON_NEAR
    assert result.merges[0].distance_m is not None and result.merges[0].distance_m < 30


def test_slightly_different_spelling_nearby_merges():
    result = dedupe(
        [place("Aoi Marushin", **HERE), place("Aoi-Marushin", source_url="https://x/2", **NEARBY)]
    )
    assert len(result.places) == 1


def test_accents_and_case_do_not_matter():
    a = place("Café de l'Été", **HERE)
    b = place("CAFE DE L'ETE", source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 1


def test_same_wikidata_id_merges_even_with_different_names():
    a = place("Kanda Shrine", wikidata_id="Q1", **HERE)
    b = place("Kanda Myojin", wikidata_id="Q1", source_url="https://x/2", **FAR)
    result = dedupe([a, b])
    assert len(result.places) == 1 and result.merges[0].reason == REASON_WIKIDATA


def test_see_and_do_count_as_the_same_kind():
    a = place("Yoyogi Park", **HERE)
    b = place(
        "Yoyogi Park", category=Category.DO, source_section="do", source_url="https://x/2", **NEARBY
    )
    assert len(dedupe([a, b]).places) == 1


def test_no_coordinates_but_same_address_merges():
    a = place("Westin Hotel", category=Category.SLEEP, address="1-4-1 Mita")
    b = place(
        "Westin Hotel", category=Category.SLEEP, address="1-4-1 Mita", source_url="https://x/2"
    )
    result = dedupe([a, b])
    assert len(result.places) == 1 and result.merges[0].reason == REASON_CORROBORATED


def test_no_coordinates_but_same_phone_merges():
    a = place("Kochoo", category=Category.EAT, phone="+81 3-5423-7000")
    b = place(
        "Kochoo",
        category=Category.EAT,
        phone="03 5423 7000".replace("03", "+81 3"),
        source_url="https://x/2",
    )
    assert len(dedupe([a, b]).places) == 1


def test_no_coordinates_but_same_specific_web_page_merges():
    a = place("Cafe Luna", category=Category.EAT, website="https://www.luna.example/shibuya")
    b = place(
        "Cafe Luna",
        category=Category.EAT,
        website="http://luna.example/shibuya/",
        source_url="https://x/2",
    )
    assert len(dedupe([a, b]).places) == 1


def test_same_id_always_merges_even_across_kinds():
    full = place("Namja Town", source_url="https://x/1", **HERE)
    stub = place(
        "Namja Town", category=Category.EAT, source_section="eat", source_url="https://x/1"
    )
    result = dedupe([full, stub])
    assert len(result.places) == 1
    assert result.places[0].category == Category.SEE  # the first (full) listing wins
    assert result.places[0].has_coordinates
    assert result.merges[0].reason == REASON_SAME_ID
    assert result.refreshed == 1 and result.duplicates_removed == 0


# ---- must NOT merge ----------------------------------------------------------------


def test_same_chain_in_different_places_stays_apart():
    result = dedupe(
        [place("Bic Camera", **HERE), place("Bic Camera", source_url="https://x/2", **FAR)]
    )
    assert len(result.places) == 2


def test_chain_homepage_alone_does_not_merge_branches():
    """Regression: two Don Quijote stores sharing only donki.com were merged."""
    a = place(
        "Don Quijote",
        category=Category.DO,
        address="4-3-3 Sotokanda",
        website="http://www.donki.com/",
    )
    b = place(
        "Don Quijote", category=Category.DO, website="https://donki.com", source_url="https://x/2"
    )
    assert len(dedupe([a, b]).places) == 2


def test_same_name_without_coordinates_or_evidence_stays_apart():
    a = place("Yoshinoya", category=Category.EAT)
    b = place("Yoshinoya", category=Category.EAT, source_url="https://x/2")
    assert len(dedupe([a, b]).places) == 2


def test_different_addresses_do_not_corroborate():
    a = place("Hands", address="Sendagaya 5-24-2")
    b = place("Hands", address="12-18 Udagawa-cho", source_url="https://x/2")
    assert len(dedupe([a, b]).places) == 2


def test_similar_names_in_the_same_building_but_different_places_stay_apart():
    a = place("Akihabara Washington Hotel", category=Category.SLEEP, **HERE)
    b = place("Remm Akihabara Hotel", category=Category.SLEEP, source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 2


def test_different_kinds_never_merge():
    hotel = place("Grand Cafe", category=Category.SLEEP, **HERE)
    cafe = place("Grand Cafe", category=Category.EAT, source_url="https://x/2", **NEARBY)
    assert len(dedupe([hotel, cafe]).places) == 2


def test_different_cities_never_merge():
    a = place("Central Park", **HERE)
    b = place("Central Park", city="Othertown", source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 2


def test_similar_names_with_different_kana_stay_apart():
    # ぱ and は differ only by a small mark; accent stripping must not erase it.
    assert normalize_name("ぱすた") != normalize_name("はすた")
    a = place("ぱすたかん", category=Category.EAT, **HERE)
    b = place("はすたかん", category=Category.EAT, source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 2


def test_short_names_one_letter_apart_stay_apart():
    a = place("Cafe A", category=Category.EAT, **HERE)
    b = place("Cafe B", category=Category.EAT, source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 2


def test_long_names_with_a_small_spelling_difference_still_merge():
    a = place("Tokyo Dome City", **HERE)
    b = place("Tokyo Dome", source_url="https://x/2", **NEARBY)
    assert len(dedupe([a, b]).places) == 1


def test_one_place_alone_is_untouched():
    p = place("Fire Museum", **HERE)
    result = dedupe([p])
    assert result.places == [p] and result.merges == []


# ---- how merging picks values --------------------------------------------------------


def test_merge_fills_gaps_and_unions_sources():
    a = place("Daigo", category=Category.EAT, description="Kaiseki.", **HERE)
    b = place(
        "Daigo",
        category=Category.EAT,
        source_url="https://x/2",
        phone="+81 3-1234-5678",
        opening_hours="11-22",
        tags=["food"],
        **NEARBY,
    )
    merged = dedupe([a, b]).places[0]
    assert merged.description == "Kaiseki."
    assert merged.phone == "+81 3-1234-5678" and merged.opening_hours == "11-22"
    assert merged.tags == ["food"]
    assert {s.url for s in merged.sources} == {a.source_url, b.source_url}


def test_merged_place_keeps_the_first_members_id():
    existing = place("Daigo", **HERE)
    new = place("Daigo", source_url="https://x/new", **NEARBY)
    assert dedupe([existing, new]).places[0].id == existing.id
    assert dedupe([new, existing]).places[0].id == new.id


def test_better_source_wins_a_conflict(monkeypatch):
    monkeypatch.setattr("app.places.dedupe.SOURCE_PRIORITY", {"wikivoyage": 10, "osm": 5})
    wv = place("Daigo", source="wikivoyage", description="From Wikivoyage.", **HERE)
    osm = place("Daigo", source="osm", description="From OSM.", **NEARBY)
    assert dedupe([osm, wv]).places[0].description == "From Wikivoyage."
    assert dedupe([osm, wv]).places[0].source == "wikivoyage"


def test_newer_fetch_wins_within_the_same_source():
    old = place("Daigo", description="old", **HERE)
    new = place(
        "Daigo",
        description="new",
        source_url="https://x/2",
        fetched_at=WHEN + timedelta(days=1),
        **NEARBY,
    )
    assert dedupe([old, new]).places[0].description == "new"


@pytest.mark.parametrize("count", [2, 5])
def test_three_way_chain_collapses_to_one(count):
    members = [place("Daigo", source_url=f"https://x/{i}", **HERE) for i in range(count)]
    result = dedupe(members)
    assert len(result.places) == 1 and result.duplicates_removed == count - 1


def test_result_keeps_input_order():
    result = dedupe(
        [
            place("B", **HERE),
            place("A", source_url="https://x/2", **FAR),
            place("B", source_url="https://x/3", **NEARBY),
        ]
    )
    assert names(result) == ["B", "A"]
