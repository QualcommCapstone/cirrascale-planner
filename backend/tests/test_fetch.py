"""PoliteFetcher: robots.txt, delays, retries, and the User-Agent."""

from __future__ import annotations

import pytest

from app.scraping.fetch import FetchFailed, RobotsDisallowed
from tests.conftest import FakeHttp, FakeResponse

SITE = "https://example.org"
ROBOTS = f"{SITE}/robots.txt"
PAGE = f"{SITE}/wiki/Page"


def test_fetches_page_and_sends_our_user_agent(make_fetcher):
    http = FakeHttp(
        {ROBOTS: FakeResponse(200, "User-agent: *\nAllow: /"), PAGE: FakeResponse(200, "<p>hi</p>")}
    )
    fetcher = make_fetcher(http, user_agent="TestBot/1.0")

    response = fetcher.fetch(PAGE)

    assert response.status == 200
    assert http.urls() == [ROBOTS, PAGE]
    assert all(ua == "TestBot/1.0" for _, _, ua in http.calls)


def test_robots_disallow_blocks_without_requesting_the_page(make_fetcher):
    http = FakeHttp(
        {ROBOTS: FakeResponse(200, "User-agent: *\nDisallow: /w/"), PAGE: FakeResponse(200)}
    )
    fetcher = make_fetcher(http)

    with pytest.raises(RobotsDisallowed):
        fetcher.fetch(f"{SITE}/w/api.php?action=parse")
    assert http.urls() == [ROBOTS]  # never asked for the blocked page


def test_robots_is_fetched_once_per_site(make_fetcher):
    http = FakeHttp(
        {ROBOTS: FakeResponse(200, ""), PAGE: FakeResponse(200), f"{SITE}/b": FakeResponse(200)}
    )
    fetcher = make_fetcher(http, min_delay_s=0)

    fetcher.fetch(PAGE)
    fetcher.fetch(f"{SITE}/b")

    assert http.urls().count(ROBOTS) == 1


def test_missing_robots_txt_means_allowed(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(404), PAGE: FakeResponse(200)})
    assert make_fetcher(http).fetch(PAGE).status == 200


def test_robots_server_error_blocks_the_site(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(503), PAGE: FakeResponse(200)})
    fetcher = make_fetcher(http, max_attempts=2)

    with pytest.raises(RobotsDisallowed):
        fetcher.fetch(PAGE)
    assert PAGE not in http.urls()


def test_waits_min_delay_between_requests_to_same_site(make_fetcher, clock):
    http = FakeHttp({ROBOTS: FakeResponse(200, ""), PAGE: FakeResponse(200)})
    fetcher = make_fetcher(http, min_delay_s=3.0)

    fetcher.fetch(PAGE)  # robots.txt, then page (waits 3s after robots)
    fetcher.fetch(PAGE)  # waits 3s again

    assert clock.sleeps == [3.0, 3.0]


def test_crawl_delay_longer_than_ours_is_respected(make_fetcher, clock):
    http = FakeHttp(
        {ROBOTS: FakeResponse(200, "User-agent: *\nCrawl-delay: 10"), PAGE: FakeResponse(200)}
    )
    fetcher = make_fetcher(http, min_delay_s=3.0)

    fetcher.fetch(PAGE)
    fetcher.fetch(PAGE)

    assert clock.sleeps[-1] == 10.0


def test_different_sites_do_not_wait_for_each_other(make_fetcher, clock):
    other = "https://other.org"
    http = FakeHttp(
        {
            ROBOTS: FakeResponse(404),
            PAGE: FakeResponse(200),
            f"{other}/robots.txt": FakeResponse(404),
            f"{other}/x": FakeResponse(200),
        }
    )
    fetcher = make_fetcher(http, min_delay_s=3.0)

    fetcher.fetch(PAGE)
    sleeps_before = len(clock.sleeps)
    fetcher.fetch(f"{other}/x")

    assert len(clock.sleeps) == sleeps_before + 1  # only other.org's own robots->page gap


def test_retries_on_503_then_succeeds(make_fetcher, clock):
    http = FakeHttp(
        {ROBOTS: FakeResponse(404), PAGE: [FakeResponse(503), FakeResponse(503), FakeResponse(200)]}
    )
    fetcher = make_fetcher(http, min_delay_s=0, backoff_s=2.0, max_attempts=3)

    assert fetcher.fetch(PAGE).status == 200
    assert http.urls().count(PAGE) == 3
    assert clock.sleeps == [2.0, 4.0]  # backoff doubles


def test_retry_after_header_is_used(make_fetcher, clock):
    http = FakeHttp(
        {
            ROBOTS: FakeResponse(404),
            PAGE: [FakeResponse(429, headers={"retry-after": "7"}), FakeResponse(200)],
        }
    )
    fetcher = make_fetcher(http, min_delay_s=0)

    fetcher.fetch(PAGE)

    assert 7.0 in clock.sleeps


def test_retries_network_errors_then_gives_up(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(404), PAGE: ConnectionError("connection reset")})
    fetcher = make_fetcher(http, min_delay_s=0, max_attempts=3)

    with pytest.raises(FetchFailed, match="gave up after 3 attempts"):
        fetcher.fetch(PAGE)
    assert http.urls().count(PAGE) == 3


def test_404_fails_immediately_without_retry(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(404), PAGE: FakeResponse(404)})
    fetcher = make_fetcher(http, max_attempts=3)

    with pytest.raises(FetchFailed, match="HTTP 404"):
        fetcher.fetch(PAGE)
    assert http.urls().count(PAGE) == 1


def test_browser_kind_is_passed_through(make_fetcher):
    http = FakeHttp({ROBOTS: FakeResponse(404), PAGE: FakeResponse(200)})
    make_fetcher(http).fetch(PAGE, kind="browser")

    assert (PAGE, "browser") in [(url, kind) for url, kind, _ in http.calls]
    assert (ROBOTS, "static") in [
        (url, kind) for url, kind, _ in http.calls
    ]  # robots is always plain HTTP
