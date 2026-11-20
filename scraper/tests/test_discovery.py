"""Discovery: URL normalization, eligibility, the DuckDuckGo provider, and the run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import FakeClock
from travel_scraper.discovery.base import DiscoveryError, SearchHit
from travel_scraper.discovery.discover import build_queries, discover, read_discovered
from travel_scraper.discovery.duckduckgo import DuckDuckGoProvider
from travel_scraper.discovery.urls import (
    REASON_AGGREGATOR,
    REASON_NON_HTML,
    REASON_OK,
    REASON_OK_OFFICIAL,
    REASON_OWN_SOURCE,
    REASON_SOCIAL,
    eligibility,
    normalize_url,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://WWW.Example.com/Path/?utm_source=x&id=3#top",
            "https://www.example.com/Path/?id=3",
        ),
        ("http://example.com:80/a/", "http://example.com/a/"),
        ("https://example.com", "https://example.com/"),
        ("https://example.com/?fbclid=abc&gclid=1", "https://example.com/"),
        ("ftp://example.com/file", None),
        ("not a url", None),
    ],
)
def test_normalize_url(raw: str, expected: str | None) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    ("url", "eligible", "reason"),
    [
        ("https://www.tnm.jp/", True, REASON_OK),
        ("https://www.gotokyo.org/en/", True, REASON_OK_OFFICIAL),
        ("https://www.city.taito.lg.jp/", True, REASON_OK_OFFICIAL),
        ("https://www.japan.travel/", True, REASON_OK),
        ("https://www.tripadvisor.com/Attractions-g1", False, REASON_AGGREGATOR),
        ("https://jp.tripadvisor.com/x", False, REASON_AGGREGATOR),
        ("https://www.yelp.co.jp/biz/x", False, REASON_AGGREGATOR),
        ("https://www.booking.com/hotel", False, REASON_AGGREGATOR),
        ("https://tabelog.com/en/tokyo", False, REASON_AGGREGATOR),
        ("https://www.google.com/maps/place/x", False, REASON_AGGREGATOR),
        ("https://www.instagram.com/x", False, REASON_SOCIAL),
        ("https://m.youtube.com/watch?v=1", False, REASON_SOCIAL),
        ("https://en.wikipedia.org/wiki/Tokyo", False, REASON_OWN_SOURCE),
        ("https://en.wikivoyage.org/wiki/Tokyo", False, REASON_OWN_SOURCE),
        ("https://example.com/guide.pdf", False, REASON_NON_HTML),
    ],
)
def test_eligibility(url: str, eligible: bool, reason: str) -> None:
    check = eligibility(url)
    assert (check.eligible, check.reason) == (eligible, reason)


def test_official_sites_get_top_priority() -> None:
    assert eligibility("https://www.gotokyo.org/").priority == 0
    assert eligibility("https://www.tnm.jp/").priority == 1


def test_build_queries() -> None:
    queries = build_queries("Tokyo", "Japan", ["museums", "restaurants"])
    assert queries[0] == ("museums", "Tokyo Japan museums official website")
    assert ("restaurants", "Tokyo Japan vegetarian restaurants") in queries
    with pytest.raises(ValueError, match="unknown categories"):
        build_queries("Tokyo", "Japan", ["spaceports"])


class FakeDDGS:
    def __init__(self, rows: list[dict[str, Any]] | Exception) -> None:
        self.rows = rows
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def text(self, query: str, **kw: Any) -> list[dict[str, Any]]:
        self.calls.append((query, kw))
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows


def test_duckduckgo_provider_pins_backend_and_waits(clock: FakeClock) -> None:
    fake = FakeDDGS([{"title": "TNM", "href": "https://www.tnm.jp/", "body": "museum"}, {"x": 1}])
    provider = DuckDuckGoProvider(
        delay_s=3, client_factory=lambda: fake, sleep=clock.sleep, clock=clock.time
    )
    hits = provider.search("q1", 5)
    provider.search("q2", 5)
    assert hits == [SearchHit(url="https://www.tnm.jp/", title="TNM", snippet="museum")]
    assert fake.calls[0][1]["backend"] == "duckduckgo"
    assert fake.calls[0][1]["max_results"] == 5
    assert clock.sleeps == [3]


def test_duckduckgo_errors_become_discovery_errors(clock: FakeClock) -> None:
    provider = DuckDuckGoProvider(
        client_factory=lambda: FakeDDGS(RuntimeError("ratelimit")),
        sleep=clock.sleep,
        clock=clock.time,
    )
    with pytest.raises(DiscoveryError, match="ratelimit"):
        provider.search("q", 5)


class ScriptedProvider:
    name = "scripted"

    def __init__(self, results: dict[str, list[SearchHit] | Exception]) -> None:
        self.results = results

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        for marker, value in self.results.items():
            if marker in query:
                if isinstance(value, Exception):
                    raise value
                return value[:max_results]
        return []


def test_discover_dedupes_filters_and_survives_failures(tmp_path: Path) -> None:
    provider = ScriptedProvider({
        "museums": [SearchHit("https://www.tnm.jp/?utm_source=ddg"), SearchHit("https://www.tnm.jp/"),
                    SearchHit("https://www.tripadvisor.com/x"), SearchHit("https://www.gotokyo.org/en")],
        "restaurants": DiscoveryError("rate limited"),
    })  # fmt: skip
    result = discover("Tokyo", "Japan", ["museums", "restaurants"], provider)
    assert [u.url for u in result.urls] == [
        "https://www.tnm.jp/", "https://www.tripadvisor.com/x", "https://www.gotokyo.org/en",
    ]  # fmt: skip
    assert [u.url for u in result.eligible] == ["https://www.gotokyo.org/en", "https://www.tnm.jp/"]
    assert len(result.failed_queries) == 2  # both restaurant queries
    assert result.urls[0].provider == "scripted"

    path = result.write(tmp_path / "tokyo.jsonl")
    again = read_discovered(path)
    assert [u.url for u in again] == [u.url for u in result.urls]
    assert again[0].discovered_at == result.urls[0].discovered_at
