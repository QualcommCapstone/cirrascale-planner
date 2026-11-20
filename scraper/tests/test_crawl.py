"""Crawl: JSON-LD / microdata extraction, the spider callback, and the collector."""

from __future__ import annotations

from typing import Any

import pytest
from scrapy.http import HtmlResponse, Request

from tests.conftest import fixture_text
from travel_scraper.crawl.extract import (
    extract_places,
    from_jsonld,
    from_microdata,
    looks_client_rendered,
    opening_hours,
    place_type,
)
from travel_scraper.crawl.run import (
    SKIP_DUPLICATE,
    SKIP_FAR,
    SKIP_NO_PLACE,
    CrawlCollector,
    distance_km,
    to_listing,
)
from travel_scraper.crawl.spider import PlaceSpider, build_settings
from travel_scraper.handoff import now

PAGE = "https://museum.example.jp/en/"


# ---- extraction ------------------------------------------------------------------


def test_jsonld_graph_and_multiple_blocks() -> None:
    places = from_jsonld(fixture_text("jsonld_page.html"), PAGE)
    assert [p.name for p in places] == ["Example Art Museum", "Museum Cafe Ramen"]
    museum, cafe = places
    assert museum.section == "see"
    assert museum.subsection == "Museum"
    assert museum.address == "1-2-3 Ueno, Taito, 110-0007"
    assert (museum.lat, museum.lng) == (35.715, 139.774)
    assert museum.hours == "Tu,We 09:30-17:00"
    assert museum.price == "¥1000"
    assert museum.wikidata_id == "Q11111111"
    assert museum.website == PAGE  # no url in the node: the page itself
    assert cafe.section == "eat"
    assert cafe.subsection == "Ramen restaurant"
    assert cafe.hours == "Mo-Fr 11:00-15:00"
    assert cafe.website == "https://museum.example.jp/cafe"


def test_descriptions_are_never_copied() -> None:
    places = extract_places(fixture_text("jsonld_page.html"), PAGE)
    listing = to_listing(places[0], PAGE, "Tokyo", now())
    assert listing.description is None
    assert "marketing" not in listing.model_dump_json()


def test_microdata_fallback() -> None:
    html = fixture_text("microdata_page.html")
    assert from_jsonld(html, PAGE) == []
    places = from_microdata(html, PAGE)
    assert len(places) == 1
    sushi = places[0]
    assert sushi.name == "Sushi Example"
    assert sushi.section == "eat"
    assert sushi.subsection == "Sushi restaurant"
    assert (sushi.lat, sushi.lng) == (35.6654, 139.7707)
    assert sushi.phone == "+81 3-1111-1111"
    assert sushi.price == "$$"
    assert sushi.method == "microdata"
    assert extract_places(html, PAGE) == places


def test_page_without_structured_data_gives_nothing() -> None:
    html = (
        "<html><body><h1>Top 10 things to do in Tokyo</h1><p>"
        + "words " * 100
        + "</p></body></html>"
    )
    assert extract_places(html, PAGE) == []
    assert not looks_client_rendered(html)


def test_client_rendered_detection() -> None:
    assert looks_client_rendered(
        '<html><body><div id="root"></div><script>app()</script></body></html>'
    )
    assert not looks_client_rendered(fixture_text("jsonld_page.html"))


@pytest.mark.parametrize(
    ("types", "expected"),
    [
        (["Museum"], ("see", "Museum")),
        (["Thing", "BarOrPub"], ("drink", "Bar")),
        (["Hotel"], ("sleep", "Hotel")),
        (["LocalBusiness"], None),  # too vague to guess
        (["Organization"], None),
    ],
)
def test_place_type(types: list[str], expected: Any) -> None:
    assert place_type(types) == expected


def test_opening_hours_variants() -> None:
    assert opening_hours({"openingHours": "Mo-Su 10:00-18:00"}) == "Mo-Su 10:00-18:00"
    spec = {
        "openingHoursSpecification": {
            "dayOfWeek": "http://schema.org/Sunday",
            "opens": "10:00",
            "closes": "16:00",
        }
    }
    assert opening_hours(spec) == "Su 10:00-16:00"
    assert opening_hours({}) is None


def test_bad_coordinates_are_dropped() -> None:
    html = (
        '<script type="application/ld+json">{"@type": "Park", "name": "P", '
        '"geo": {"latitude": "999", "longitude": "1"}}</script>'
    )
    (park,) = from_jsonld(html, PAGE)
    assert (park.lat, park.lng) == (None, None)
    assert park.section == "do"


# ---- spider -------------------------------------------------------------------------


def _response(url: str, html: str, meta: dict[str, Any] | None = None) -> HtmlResponse:
    request = Request(url, meta=meta or {})
    return HtmlResponse(url=url, body=html.encode("utf-8"), encoding="utf-8", request=request)


def test_spider_yields_places_and_follows_same_domain_place_links() -> None:
    spider = PlaceSpider(seed_urls=[PAGE])
    out = list(spider.parse(_response(PAGE, fixture_text("jsonld_page.html"))))
    items = [o for o in out if isinstance(o, dict)]
    follows = [o.url for o in out if isinstance(o, Request)]
    assert [i["place"].name for i in items] == ["Example Art Museum", "Museum Cafe Ramen"]
    assert follows == [
        "https://museum.example.jp/en/museums/annex"
    ]  # not other domains or /contact


def test_spider_reports_pages_without_places() -> None:
    spider = PlaceSpider(seed_urls=[PAGE])
    out = list(spider.parse(_response(PAGE, "<html><body><p>hello</p></body></html>")))
    assert out == [{"no_place": PAGE}]


def test_spider_retries_js_pages_with_playwright_only_when_enabled() -> None:
    js_page = '<html><body><div id="app"></div></body></html>'
    off = list(PlaceSpider(seed_urls=[PAGE]).parse(_response(PAGE, js_page)))
    assert off == [{"no_place": PAGE}]
    on = list(PlaceSpider(seed_urls=[PAGE], playwright=True).parse(_response(PAGE, js_page)))
    assert len(on) == 1 and isinstance(on[0], Request)
    assert on[0].meta["playwright"] is True
    # An already-rendered page is not rendered again.
    again = list(
        PlaceSpider(seed_urls=[PAGE], playwright=True).parse(
            _response(PAGE, js_page, meta={"playwright": True})
        )
    )
    assert again == [{"no_place": PAGE}]


def test_settings_are_polite() -> None:
    s = build_settings(user_agent="ua", delay_s=3, max_pages=40, max_depth=1, playwright=False)
    assert s["ROBOTSTXT_OBEY"] is True
    assert s["AUTOTHROTTLE_ENABLED"] is True
    assert s["CONCURRENT_REQUESTS_PER_DOMAIN"] == 1
    assert s["DOWNLOAD_DELAY"] == 3
    assert s["CLOSESPIDER_PAGECOUNT"] == 40
    assert s["DEPTH_LIMIT"] == 1
    assert s["USER_AGENT"] == "ua"
    assert "DOWNLOAD_HANDLERS" not in s
    with_js = build_settings(user_agent="ua", delay_s=3, max_pages=1, max_depth=0, playwright=True)
    assert "scrapy_playwright" in with_js["DOWNLOAD_HANDLERS"]["https"]


# ---- collector -------------------------------------------------------------------------


def test_collector_builds_result() -> None:
    museum, cafe = extract_places(fixture_text("jsonld_page.html"), PAGE)
    c = CrawlCollector(city="Tokyo", center=(35.68, 139.76))
    c.add({"place": museum, "url": PAGE})
    c.add({"place": museum, "url": PAGE})
    c.add({"place": cafe, "url": PAGE})
    c.add({"no_place": "https://museum.example.jp/en/museums/annex"})
    result = c.finish({"robotstxt/forbidden": 2, "downloader/response_status_count/404": 1})
    assert [x.name for x in result.listings] == ["Example Art Museum", "Museum Cafe Ramen"]
    assert result.listings[0].source == "web"
    assert result.listings[0].source_url == PAGE + "#example_art_museum"
    assert result.skipped == {SKIP_DUPLICATE: 1, SKIP_NO_PLACE: 1, "blocked by robots.txt": 2}
    assert result.errors == ["HTTP 404 on 1 page(s)"]
    assert len(result.pages_fetched) == 2


def test_collector_drops_places_far_from_the_city() -> None:
    (museum, _) = extract_places(fixture_text("jsonld_page.html"), PAGE)
    c = CrawlCollector(city="Osaka", center=(34.69, 135.50))
    c.add({"place": museum, "url": PAGE})
    assert c.result.listings == []
    assert c.result.skipped == {SKIP_FAR: 1}


def test_distance_km() -> None:
    assert distance_km((35.68, 139.76), (34.69, 135.50)) == pytest.approx(400, rel=0.05)
