"""Wikidata coordinate fill."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from tests.conftest import FakeClock, fixture_json
from travel_scraper.handoff import RawListing, ScrapeResult
from travel_scraper.http import ApiClient, RetryableResponse
from travel_scraper.wikidata import check_wikidata, coordinates, fill_coordinates, needs_coordinates

WHEN = datetime(2026, 11, 17, tzinfo=UTC)
URL = "https://wikidata.test/w/api.php"


def listing(name: str, **kw: Any) -> RawListing:
    values: dict[str, Any] = {
        "source": "wikivoyage", "source_url": f"https://en.wikivoyage.org/wiki/Tokyo#{name}",
        "page_url": "https://en.wikivoyage.org/wiki/Tokyo", "fetched_at": WHEN, "city": "Tokyo",
        "section": "see", "name": name,
    }  # fmt: skip
    values.update(kw)
    return RawListing(**values)


def test_coordinates_reads_p625() -> None:
    entity = fixture_json("wikidata_entities.json")["entities"]["Q653433"]
    assert coordinates(entity) == (35.71889, 139.77639)
    assert coordinates({"claims": {}}) is None
    bad = {
        "claims": {
            "P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 0, "longitude": 0}}}}]
        }
    }
    assert coordinates(bad) is None


def test_needs_coordinates() -> None:
    assert needs_coordinates(listing("a", wikidata_id="Q1"))
    assert not needs_coordinates(listing("b"))
    assert not needs_coordinates(listing("c", wikidata_id="Q1", lat=1.0, lng=2.0))
    assert not needs_coordinates(listing("d", wikidata_id="nope"))


def test_check_wikidata_maxlag_is_retryable() -> None:
    check_wikidata({"entities": {}})
    with pytest.raises(RetryableResponse) as info:
        check_wikidata({"error": {"code": "maxlag", "lag": 3}})
    assert info.value.retry_after == 3.0
    with pytest.raises(RetryableResponse):
        check_wikidata({"something": "else"})


def _client(clock: FakeClock, bodies: list[Any]) -> tuple[ApiClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = bodies.pop(0) if len(bodies) > 1 else bodies[0]
        return httpx.Response(200, json=body)

    client = ApiClient(
        user_agent="t",
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.time,
        min_delay_s=0,
        max_attempts=2,
    )
    return client, seen


def test_fill_coordinates(clock: FakeClock) -> None:
    result = ScrapeResult(source="wikivoyage", city="Tokyo", started_at=WHEN, listings=[
        listing("museum", wikidata_id="Q653433"),
        listing("no-coords-on-wikidata", wikidata_id="Q1"),
        listing("missing-entity", wikidata_id="Q999999999"),
        listing("has-coords", wikidata_id="Q653433", lat=1.0, lng=2.0),
        listing("no-id"),
    ])  # fmt: skip
    client, seen = _client(clock, [fixture_json("wikidata_entities.json")])
    report = fill_coordinates(result, client, url=URL)
    assert (report.candidates, report.filled, report.not_found) == (3, 1, 2)
    assert (result.listings[0].lat, result.listings[0].lng) == (35.71889, 139.77639)
    assert result.listings[3].lat == 1.0  # never overwritten
    params = seen[0].url.params
    assert params["action"] == "wbgetentities"
    assert params["maxlag"] == "5"
    assert set(params["ids"].split("|")) == {"Q653433", "Q1", "Q999999999"}


def test_batches_of_fifty(clock: FakeClock) -> None:
    result = ScrapeResult(
        source="wikivoyage",
        city="Tokyo",
        started_at=WHEN,
        listings=[listing(f"p{i}", wikidata_id=f"Q{i + 1}") for i in range(120)],
    )
    client, seen = _client(clock, [{"entities": {}}])
    fill_coordinates(result, client, url=URL)
    assert [len(r.url.params["ids"].split("|")) for r in seen] == [50, 50, 20]


def test_failed_batch_is_recorded(clock: FakeClock) -> None:
    result = ScrapeResult(
        source="wikivoyage",
        city="Tokyo",
        started_at=WHEN,
        listings=[listing("a", wikidata_id="Q653433")],
    )
    client, _ = _client(clock, [{"error": {"code": "maxlag", "lag": 1}}])
    report = fill_coordinates(result, client, url=URL)
    assert report.failed_batches == 1
    assert report.filled == 0
    assert result.listings[0].lat is None
    assert result.errors and result.errors[0].startswith("wikidata:")
