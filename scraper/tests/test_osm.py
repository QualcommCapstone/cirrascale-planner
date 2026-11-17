"""OSM: query building, element parsing, and a full scrape over a mocked Overpass."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest

from tests.conftest import FakeClock, fixture_json
from travel_scraper.http import ApiClient, RetryableResponse
from travel_scraper.osm.parse import (
    SKIP_DUPLICATE,
    SKIP_NO_COORDINATES,
    SKIP_NO_NAME,
    label,
    parse_elements,
    to_listing,
)
from travel_scraper.osm.query import bbox, build_query
from travel_scraper.osm.scrape import check_overpass, scrape_osm

WHEN = datetime(2026, 11, 17, tzinfo=UTC)
CENTER = (35.6812, 139.7671)


# ---- query ----------------------------------------------------------------------


def test_query_filters_on_the_server() -> None:
    q = build_query("eat", CENTER, 15, limit=1200)
    assert q.startswith("[out:json][timeout:90][bbox:35.54645,139.60121,35.81595,139.93299];")
    assert "around:" not in q  # a bbox is much cheaper for Overpass than a radius
    # eat needs wikidata, or website + opening_hours, and a name
    assert '["amenity"~"^(restaurant|cafe|food_court)$"]["wikidata"]' in q
    assert '["website"]["opening_hours"]' in q
    assert q.count('["name"];') == 2
    assert q.rstrip().endswith("out center tags 1200;")


def test_see_requires_wikidata_for_historic_and_worship_only() -> None:
    q = build_query("see", CENTER, 10, limit=10)
    assert 'nwr["historic"]["wikidata"]' in q
    assert 'nwr["amenity"="place_of_worship"]["wikidata"]' in q
    assert 'theme_park)$"]["name"];' in q  # no extra requirement


def test_parks_need_wikidata_or_website() -> None:
    q = build_query("do", CENTER, 10, limit=10)
    assert '["leisure"~"^(park|garden|nature_reserve)$"]["wikidata"]' in q
    assert '["leisure"~"^(park|garden|nature_reserve)$"]["website"]' in q


# ---- labels -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tags", "expected"),
    [
        ({"tourism": "museum"}, "Museum"),
        ({"amenity": "place_of_worship", "religion": "buddhist"}, "Buddhist temple"),
        ({"amenity": "place_of_worship", "religion": "shinto"}, "Shinto shrine"),
        ({"amenity": "place_of_worship", "religion": "christian"}, "Church"),
        ({"amenity": "place_of_worship"}, "Place of worship"),
        ({"amenity": "restaurant", "cuisine": "ramen;japanese"}, "Ramen restaurant"),
        ({"amenity": "restaurant"}, "Restaurant"),
        ({"amenity": "cafe", "diet:vegetarian": "yes"}, "Cafe (vegetarian)"),
        ({"historic": "castle"}, "Historic castle"),
        ({"historic": "yes"}, "Historic site"),
        ({"historic": "memorial", "tourism": "attraction"}, "Attraction"),
        ({"leisure": "park"}, "Park"),
        ({"shop": "department_store"}, "Department store"),
        ({"craft": "brewery"}, None),
    ],
)
def test_label(tags: dict[str, str], expected: str | None) -> None:
    assert label(tags) == expected


# ---- elements ---------------------------------------------------------------------


def test_english_name_with_local_alt_name_and_way_center() -> None:
    element = fixture_json("overpass_see.json")["elements"][0]
    listing = to_listing(element, section="see", city="Tokyo", fetched_at=WHEN)
    assert not isinstance(listing, str)
    assert listing.name == "Tokyo National Museum"
    assert listing.alt_name == "東京国立博物館"
    assert (listing.lat, listing.lng) == (35.7188, 139.7765)
    assert listing.source == "osm"
    assert listing.source_url == listing.page_url == "https://www.openstreetmap.org/way/101"
    assert listing.address == "13-9 Ueno Park, 110-8712"
    assert listing.hours == "Tu-Su 09:30-17:00"
    assert listing.wikidata_id == "Q653433"
    assert listing.subsection == "Museum"


def test_place_with_only_a_local_name_is_kept() -> None:
    element = fixture_json("overpass_see.json")["elements"][1]
    listing = to_listing(element, section="see", city="Tokyo", fetched_at=WHEN)
    assert not isinstance(listing, str)
    assert listing.name == "浅草寺"
    assert listing.alt_name is None
    assert listing.price == "free"  # fee=no
    assert listing.subsection == "Buddhist temple"


def test_parse_skips_and_counts() -> None:
    elements = fixture_json("overpass_see.json")["elements"]
    listings, skipped = parse_elements(
        elements, section="see", city="Tokyo", fetched_at=WHEN, max_items=100
    )
    assert len(listings) == 5
    assert skipped == {SKIP_NO_COORDINATES: 1, SKIP_NO_NAME: 1, SKIP_DUPLICATE: 1}


def test_cap_keeps_wikidata_places_first() -> None:
    elements = fixture_json("overpass_see.json")["elements"]
    listings, skipped = parse_elements(
        elements, section="see", city="Tokyo", fetched_at=WHEN, max_items=2
    )
    assert len(listings) == 2
    assert all(x.wikidata_id for x in listings)
    assert listings[0].name == "Tokyo National Museum"  # most filled tags
    assert any("cap of 2" in reason for reason in skipped)


def test_bad_wikidata_tag_is_dropped() -> None:
    element = {
        "type": "node",
        "id": 1,
        "lat": 1.0,
        "lon": 1.0,
        "tags": {"tourism": "museum", "name": "X", "wikidata": "not-an-id"},
    }
    listing = to_listing(element, section="see", city="T", fetched_at=WHEN)
    assert not isinstance(listing, str)
    assert listing.wikidata_id is None


# ---- full scrape ---------------------------------------------------------------------


def test_check_overpass() -> None:
    check_overpass({"elements": []})
    with pytest.raises(RetryableResponse):
        check_overpass({"elements": [], "remark": 'runtime error: Query timed out in "query"'})
    with pytest.raises(RetryableResponse):
        check_overpass({"remark": "out of memory"})


def _overpass(responses: dict[str, Any], clock: FakeClock) -> tuple[ApiClient, list[str]]:
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = parse_qs(request.content.decode())["data"][0]
        queries.append(query)
        for marker, body in responses.items():
            if marker in query:
                return body if isinstance(body, httpx.Response) else httpx.Response(200, json=body)
        return httpx.Response(200, json={"elements": []})

    client = ApiClient(
        user_agent="t",
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.time,
        min_delay_s=0,
        max_attempts=2,
    )
    return client, queries


def test_scrape_runs_one_query_per_section(clock: FakeClock) -> None:
    client, queries = _overpass(
        {'"tourism"~"^(attraction': fixture_json("overpass_see.json")}, clock
    )
    result = scrape_osm("Tokyo", CENTER, client, overpass_url="https://overpass.test/api")
    assert len(queries) == 6
    assert len(result.listings) == 5
    assert {x.section for x in result.listings} == {"see"}
    assert result.errors == []
    assert result.source == "osm"
    assert result.finished_at is not None


def test_failed_section_contributes_nothing(clock: FakeClock) -> None:
    partial = {
        "elements": [
            {
                "type": "node",
                "id": 9,
                "lat": 1,
                "lon": 1,
                "tags": {"amenity": "bar", "name": "Half"},
            }
        ],
        "remark": "runtime error: Query timed out",
    }
    client, _ = _overpass(
        {'"amenity"~"^(bar': partial, '"tourism"~"^(attraction': fixture_json("overpass_see.json")},
        clock,
    )
    result = scrape_osm("Tokyo", CENTER, client, overpass_url="https://overpass.test/api")
    assert not any(x.section == "drink" for x in result.listings)
    assert any(e.startswith("osm drink:") for e in result.errors)
    assert len(result.listings) == 5  # other sections still ran


def test_bbox_is_square_in_km() -> None:
    s, w, n, e = bbox(CENTER, 15)
    assert n - s == pytest.approx(30 / 111.32)
    assert e - w > n - s  # longitude degrees are shorter away from the equator
    assert bbox((89.9, 0.0), 50)[2] == 90.0  # clamped at the pole
