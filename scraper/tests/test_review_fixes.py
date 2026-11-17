"""Regression tests for bugs found in code review (one test per finding)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from scrapy.http import HtmlResponse, Request

from tests.conftest import FakeClock
from travel_scraper.crawl.extract import ExtractedPlace, from_microdata
from travel_scraper.crawl.run import CrawlCollector, anchor
from travel_scraper.crawl.spider import PlaceSpider
from travel_scraper.discovery.urls import dedupe_key, normalize_url
from travel_scraper.handoff import RawListing, ScrapeResult
from travel_scraper.http import MAX_RETRY_AFTER_S, ApiClient, ApiFailed
from travel_scraper.wikidata import check_wikidata, fill_coordinates

WHEN = datetime(2026, 11, 17, tzinfo=UTC)
PAGE = "https://www.example.jp/spots/"


def test_non_ascii_names_get_distinct_anchors() -> None:
    assert anchor("東京タワー") != anchor("浅草寺")
    assert anchor("Tokyo  Tower") == "tokyo_tower"
    c = CrawlCollector(city="Tokyo")
    for name in ("東京タワー", "浅草寺"):
        c.add(
            {
                "place": ExtractedPlace(name=name, section="see", subsection="Attraction"),
                "url": PAGE,
            }
        )
    assert [x.name for x in c.result.listings] == ["東京タワー", "浅草寺"]
    assert len({x.source_url for x in c.result.listings}) == 2


def _links(seed: str, page_url: str, hrefs: list[str]) -> list[str]:
    html = "<html><body>" + "".join(f'<a href="{h}">x</a>' for h in hrefs) + "</body></html>"
    response = HtmlResponse(
        url=page_url, body=html.encode(), encoding="utf-8", request=Request(page_url)
    )
    out = PlaceSpider(seed_urls=[seed]).parse(response)
    return [o.url for o in out if isinstance(o, Request)]


def test_links_on_www_and_apex_hosts_are_both_followed() -> None:
    # Seed without www, site redirects to www: links still count as the same site.
    assert _links(
        "https://gotokyo.org/en",
        "https://www.gotokyo.org/en",
        ["https://www.gotokyo.org/en/spots/1"],
    ) == ["https://www.gotokyo.org/en/spots/1"]
    # And the other way round, plus subdomains; other sites are never followed.
    assert _links("https://www.gotokyo.org/", "https://www.gotokyo.org/",
                  ["https://gotokyo.org/spots/2", "https://en.gotokyo.org/spots/3",
                   "https://evil-gotokyo.org/spots/4"]) == [
        "https://gotokyo.org/spots/2", "https://en.gotokyo.org/spots/3",
    ]  # fmt: skip


def test_crawled_url_keeps_www_and_trailing_slash() -> None:
    assert normalize_url("https://www.some-museum.jp/en/") == "https://www.some-museum.jp/en/"
    assert dedupe_key("https://www.some-museum.jp/en/") == dedupe_key("http://some-museum.jp/en")


def test_wikidata_redirected_ids_are_filled(clock: FakeClock) -> None:
    body = {"entities": {"Q456": {
        "id": "Q456", "redirects": {"from": "Q123", "to": "Q456"},
        "claims": {"P625": [
            {"mainsnak": {"datavalue": {"value": {"latitude": 35.1, "longitude": 139.2}}}}
        ]},
    }}}  # fmt: skip
    client = ApiClient(
        user_agent="t",
        min_delay_s=0,
        sleep=clock.sleep,
        clock=clock.time,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)),
    )
    listing = RawListing(
        source="wikivoyage",
        source_url="https://en.wikivoyage.org/wiki/T#a",
        page_url="https://en.wikivoyage.org/wiki/T",
        fetched_at=WHEN,
        city="Tokyo",
        section="see",
        name="Old id place",
        wikidata_id="Q123",
    )
    result = ScrapeResult(source="wikivoyage", city="Tokyo", started_at=WHEN, listings=[listing])
    report = fill_coordinates(result, client, url="https://wikidata.test/w/api.php")
    assert report.filled == 1
    assert (listing.lat, listing.lng) == (35.1, 139.2)


def test_permanent_wikidata_errors_are_not_retried(clock: FakeClock) -> None:
    with pytest.raises(ApiFailed):
        check_wikidata({"error": {"code": "no-such-entity"}})
    calls: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"error": {"code": "param-illegal"}})

    client = ApiClient(
        user_agent="t",
        min_delay_s=0,
        sleep=clock.sleep,
        clock=clock.time,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ApiFailed):
        client.get_json("https://wikidata.test/w/api.php", check=check_wikidata)
    assert len(calls) == 1


def test_retry_after_is_capped(clock: FakeClock) -> None:
    responses = [
        httpx.Response(429, headers={"Retry-After": "86400"}),
        httpx.Response(200, json={}),
    ]
    client = ApiClient(
        user_agent="t",
        min_delay_s=0,
        sleep=clock.sleep,
        clock=clock.time,
        transport=httpx.MockTransport(lambda r: responses.pop(0)),
    )
    client.get_json("https://api.test/x")
    assert clock.sleeps == [MAX_RETRY_AFTER_S]


NESTED = """
<div itemscope itemtype="https://schema.org/Restaurant">
  <div itemprop="review" itemscope itemtype="https://schema.org/Review">
    <span itemprop="author" itemscope itemtype="https://schema.org/Person">
      <span itemprop="name">Jane Reviewer</span><span itemprop="telephone">000</span>
    </span>
  </div>
  <h2 itemprop="name">Real Ramen Shop</h2>
  <span itemprop="telephone">+81 3-2222-2222</span>
</div>
<div itemscope itemtype="https://schema.org/Restaurant">
  <h2 itemprop="name">Real Ramen Shop</h2><span itemprop="telephone">+81 3-2222-2222</span>
</div>
"""


def test_microdata_ignores_nested_items_and_dedupes() -> None:
    places = from_microdata(NESTED, PAGE)
    assert len(places) == 1  # the same restaurant twice on the page
    assert places[0].name == "Real Ramen Shop"
    assert places[0].phone == "+81 3-2222-2222"
    assert places[0].method == "microdata"
