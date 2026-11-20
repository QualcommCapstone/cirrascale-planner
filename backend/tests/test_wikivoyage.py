"""Wikivoyage parser and the city scrape run."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pytest
from scrapling.parser import Selector

from app.scraping.fetch import PoliteFetcher
from app.scraping.wikivoyage import (
    SKIP_NO_NAME,
    SKIP_NOT_A_PLACE,
    article_url,
    find_district_titles,
    parse_listings,
    scrape_city,
    title_from_url,
)
from tests.conftest import FakeHttp, FakeResponse, fixture_html

WHEN = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
PAGE_URL = "https://en.wikivoyage.org/wiki/Testville"
ROBOTS = "https://en.wikivoyage.org/robots.txt"


@pytest.fixture
def page() -> Selector:
    return Selector(fixture_html("wikivoyage_city.html"), url=PAGE_URL)


@pytest.fixture
def listings(page):
    found, _ = parse_listings(
        page, page_url=PAGE_URL, city="Testville", district=None, fetched_at=WHEN
    )
    return {item.name: item for item in found}


# ---- URLs -------------------------------------------------------------------


def test_article_url_handles_spaces_and_case():
    assert article_url("san Diego") == "https://en.wikivoyage.org/wiki/San_Diego"
    assert article_url("Tokyo/Shinjuku") == "https://en.wikivoyage.org/wiki/Tokyo/Shinjuku"


def test_article_url_escapes_non_ascii():
    assert article_url("Tokyo/Ōimachi") == "https://en.wikivoyage.org/wiki/Tokyo/%C5%8Cimachi"
    assert title_from_url(article_url("Tokyo/Ōimachi")) == "Tokyo/Ōimachi"


# ---- parsing ----------------------------------------------------------------


def test_reads_all_fields_of_a_full_listing(listings):
    museum = listings["Fire Museum"]
    assert museum.section == "see"
    assert museum.subsection is None
    assert museum.alt_name == "消防博物館"
    assert museum.address == "Yotsuya 4-10"
    assert museum.directions == "just outside the station"
    assert (museum.lat, museum.lng) == (35.68836, 139.7202)
    assert museum.phone == "+81 3-3353-9119"
    assert museum.website == "https://museum.example.org/"
    assert museum.hours == "09:30-17:00, closed on Mondays"
    assert museum.price == "Free"
    assert museum.wikidata_id == "Q11559505"
    assert museum.last_edit == "updated Dec 2023"


def test_cleans_whitespace_and_keeps_inline_text(listings):
    assert listings["Fire Museum"].name == "Fire Museum"
    assert listings["Fire Museum"].description == "Three fire-fighting helicopters, ten trucks."


def test_every_listing_has_its_own_source_link_and_date(listings):
    museum = listings["Fire Museum"]
    assert museum.source == "wikivoyage"
    assert museum.source_url == f"{PAGE_URL}#Fire_Museum"
    assert museum.page_url == PAGE_URL
    assert museum.fetched_at == WHEN


def test_bad_coordinates_become_none_instead_of_crashing(listings):
    park = listings["Bad Coords Park"]
    assert park.lat is None and park.lng is None
    assert park.wikidata_id == "Q42"  # falls back to the Wikidata link


def test_missing_fields_are_none(listings):
    pasta = listings["Pasutakan"]
    assert pasta.price == "¥1200"
    assert pasta.address is None and pasta.hours is None and pasta.lat is None


def test_empty_description_is_none(listings):
    assert listings["Sakura Hotel"].description is None


def test_subsection_uses_visible_heading_not_repeated_id(listings):
    assert listings["Pasutakan"].subsection == "Budget"
    assert listings["Sakura Hotel"].section == "sleep"
    assert listings["Sakura Hotel"].subsection == "Budget"  # not "Budget 2"


def test_skips_nameless_and_non_place_listings(page, listings):
    _, skipped = parse_listings(
        page, page_url=PAGE_URL, city="Testville", district=None, fetched_at=WHEN
    )
    assert "Testville Airport" not in listings  # under "Get in"
    assert "Tourist Info" not in listings  # under "Connect"
    assert skipped == {SKIP_NOT_A_PLACE: 2, SKIP_NO_NAME: 1}  # airport + tourist info; nameless
    assert set(listings) == {"Fire Museum", "Bad Coords Park", "Pasutakan", "Sakura Hotel"}


def _combined_page(maplink_group: str | None) -> Selector:
    marker = ""
    if maplink_group:
        data = json.dumps({"attrs": {"group": maplink_group}})
        marker = f"<a class='mw-kartographer-maplink' data-mw='{data}'>1</a>"
    html = f"""<section aria-labelledby="Eat_and_drink"><h2 id="Eat_and_drink">Eat and drink</h2>
    <bdi class="vcard">{marker}<span id="a" class="fn org listing-name">Bar or Diner</span></bdi>
    </section>"""
    return Selector(html, url="")


@pytest.mark.parametrize(("group", "expected"), [("drink", "drink"), ("eat", "eat"), (None, "eat")])
def test_combined_eat_and_drink_heading_uses_marker_type(group, expected):
    found, skipped = parse_listings(
        _combined_page(group), page_url="u", city="c", district=None, fetched_at=WHEN
    )
    assert [item.section for item in found] == [expected]
    assert not skipped


def test_messy_html_does_not_crash():
    for html in [
        "",
        "<html>",
        '<bdi class="vcard"><span class="listing-name">',
        "<section aria-labelledby='See'><bdi class='vcard'></bdi>",
    ]:
        found, _ = parse_listings(
            Selector(html or "<html></html>", url=""),
            page_url="u",
            city="c",
            district=None,
            fetched_at=WHEN,
        )
        assert found == []


def test_finds_district_pages_once_each_in_order(page):
    assert find_district_titles(page, "Testville") == ["Testville/Old Town", "Testville/Harbor"]


# ---- full scrape run (fake network) ------------------------------------------


def _district_page(title: str, name: str) -> str:
    return f"""<html><head><link rel="canonical" href="{article_url(title)}"/></head><body>
    <section aria-labelledby="Do"><h2 id="Do">Do</h2>
    <bdi class="vcard"><span id="x" class="fn org listing-name">{name}</span></bdi>
    </section></body></html>"""


def test_scrape_city_follows_districts_and_keeps_going_after_errors(make_fetcher):
    http = FakeHttp(
        {
            ROBOTS: FakeResponse(200, "User-agent: *\nDisallow: /w/"),
            PAGE_URL: FakeResponse(200, fixture_html("wikivoyage_city.html")),
            article_url("Testville/Old Town"): FakeResponse(500),
            article_url("Testville/Harbor"): FakeResponse(
                200, _district_page("Testville/Harbor", "Boat Tour")
            ),
        }
    )
    fetcher: PoliteFetcher = make_fetcher(http, max_attempts=2)

    result = scrape_city("Testville", fetcher)

    names = {item.name: item for item in result.listings}
    assert "Fire Museum" in names
    assert names["Boat Tour"].district == "Harbor"
    assert names["Boat Tour"].source_url == article_url("Testville/Harbor") + "#x"
    assert len(result.pages_fetched) == 2
    assert len(result.errors) == 1 and "Old_Town" in result.errors[0]
    assert result.finished_at is not None


def test_scrape_city_respects_max_districts_and_no_districts(make_fetcher):
    http = FakeHttp(
        {
            ROBOTS: FakeResponse(404),
            PAGE_URL: FakeResponse(200, fixture_html("wikivoyage_city.html")),
        }
    )

    scrape_city("Testville", make_fetcher(http), max_districts=1)
    assert article_url("Testville/Harbor") not in http.urls()
    assert article_url("Testville/Old Town") in http.urls()

    http2 = FakeHttp(
        {
            ROBOTS: FakeResponse(404),
            PAGE_URL: FakeResponse(200, fixture_html("wikivoyage_city.html")),
        }
    )
    scrape_city("Testville", make_fetcher(http2), include_districts=False)
    assert http2.urls() == [ROBOTS, PAGE_URL]


def test_scrape_city_reports_missing_city(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(404)})
    result = scrape_city("Nowhereville", make_fetcher(http))
    assert result.listings == []
    assert "HTTP 404" in result.errors[0]


# ---- live check (off by default) -------------------------------------------


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to hit Wikivoyage"
)
def test_live_small_city():
    result = scrape_city("Sedona", PoliteFetcher(), include_districts=False)
    assert result.listings, result.errors
    assert all(
        item.source_url.startswith("https://en.wikivoyage.org/wiki/") for item in result.listings
    )
