"""Polite page fetching on top of Scrapling.

Every scraper in this package gets pages through `PoliteFetcher`, which adds the
house rules on top of Scrapling's fetchers:

1. Check robots.txt first. If a page is disallowed, we don't fetch it.
2. Wait between requests to the same site (our minimum delay, or the site's
   Crawl-delay if that is longer).
3. Retry on network errors, 429 (too many requests), and 5xx errors, waiting a
   bit longer each time. Other errors (like 404) fail right away.
4. Send an honest User-Agent that says who we are.

Which Scrapling fetcher to use (Scrapling >= 0.5):
- "static"  -> `Fetcher`: a plain HTTP request. Fast. Use this for normal pages.
- "browser" -> `StealthyFetcher`: a real headless browser. Use this for pages
  that need JavaScript to load or that block simple bots. Needs a one-time
  `uv run scrapling install` to download the browser.
  (Scrapling 0.5 removed `DynamicFetcher`; `StealthyFetcher` replaces it.)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from protego import Protego

log = logging.getLogger(__name__)

FetcherKind = Literal["static", "browser"]

DEFAULT_USER_AGENT = (
    "AI100TravelPlanner/0.1 "
    "(ASU capstone student project; https://github.com/QualcommCapstone/cirrascale-planner)"
)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class PageResponse(Protocol):
    """The parts of a Scrapling `Response` we rely on."""

    @property
    def status(self) -> int: ...
    @property
    def body(self) -> bytes: ...
    @property
    def headers(self) -> Any: ...

    def css(self, selector: str) -> Any: ...


# A function that does one raw request: (url, kind, user_agent, timeout_s) -> response.
HttpGet = Callable[[str, FetcherKind, str, float], PageResponse]


class RobotsDisallowed(Exception):
    """robots.txt says we may not fetch this URL."""


class FetchFailed(Exception):
    """We could not get the page, even after retrying."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


def scrapling_get(url: str, kind: FetcherKind, user_agent: str, timeout_s: float) -> PageResponse:
    """Do one request with the right Scrapling fetcher. Retries are handled by the caller."""
    if kind == "static":
        from scrapling.fetchers import Fetcher

        response: PageResponse = Fetcher.get(
            url,
            headers={"User-Agent": user_agent},
            stealthy_headers=False,  # don't fake browser headers or a Google referer
            timeout=timeout_s,
            retries=1,
        )
        return response

    from scrapling.fetchers import StealthyFetcher

    response = StealthyFetcher.fetch(
        url,
        headless=True,
        useragent=user_agent,
        google_search=False,  # don't fake a Google referer
        network_idle=True,  # wait for JavaScript-loaded content
        timeout=int(timeout_s * 1000),  # browser timeouts are in milliseconds
        retries=1,
    )
    return response


@dataclass
class _Robots:
    parser: Protego | None  # None means "allow everything" (no robots.txt)
    blocked: bool = False  # True means "robots.txt failed to load, so stay away"


class PoliteFetcher:
    """Fetch pages while respecting robots.txt, rate limits, and retry rules."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        min_delay_s: float = 3.0,
        max_attempts: int = 3,
        backoff_s: float = 2.0,
        timeout_s: float = 30.0,
        http_get: HttpGet = scrapling_get,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self.min_delay_s = min_delay_s
        self.max_attempts = max(1, max_attempts)
        self.backoff_s = backoff_s
        self.timeout_s = timeout_s
        self._http_get = http_get
        self._sleep = sleep
        self._clock = clock
        self._robots: dict[str, _Robots] = {}
        self._last_request: dict[str, float] = {}

    # ---- public -----------------------------------------------------------

    def fetch(self, url: str, kind: FetcherKind = "static") -> PageResponse:
        """Fetch one page. Raises `RobotsDisallowed` or `FetchFailed`."""
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        return self._fetch_with_retries(url, kind)

    def allowed(self, url: str) -> bool:
        robots = self._robots_for(url)
        if robots.blocked:
            return False
        if robots.parser is None:
            return True
        return bool(robots.parser.can_fetch(url, self.user_agent))

    # ---- internals --------------------------------------------------------

    def _fetch_with_retries(self, url: str, kind: FetcherKind) -> PageResponse:
        last_reason = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            self._wait_turn(url)
            try:
                response = self._http_get(url, kind, self.user_agent, self.timeout_s)
            except Exception as exc:  # network errors, timeouts, browser crashes
                last_reason = f"{type(exc).__name__}: {exc}"
                retry_after = None
            else:
                if 200 <= response.status < 300:
                    return response
                last_reason = f"HTTP {response.status}"
                if response.status not in RETRY_STATUSES:
                    raise FetchFailed(url, last_reason)
                retry_after = _retry_after_seconds(response)

            if attempt < self.max_attempts:
                wait = (
                    retry_after if retry_after is not None else self.backoff_s * 2 ** (attempt - 1)
                )
                log.warning(
                    "Attempt %d for %s failed (%s); retrying in %.1fs",
                    attempt,
                    url,
                    last_reason,
                    wait,
                )
                self._sleep(wait)

        raise FetchFailed(url, f"gave up after {self.max_attempts} attempts ({last_reason})")

    def _wait_turn(self, url: str) -> None:
        """Sleep until enough time has passed since our last request to this site."""
        host = _host(url)
        delay = self._delay_for(url)
        last = self._last_request.get(host)
        if last is not None:
            remaining = last + delay - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last_request[host] = self._clock()

    def _delay_for(self, url: str) -> float:
        robots = self._robots.get(_host(url))
        crawl_delay = None
        if robots is not None and robots.parser is not None:
            crawl_delay = robots.parser.crawl_delay(self.user_agent)
        return max(self.min_delay_s, float(crawl_delay or 0))

    def _robots_for(self, url: str) -> _Robots:
        host = _host(url)
        if host in self._robots:
            return self._robots[host]

        parts = urlsplit(url)
        robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
        try:
            response = self._fetch_with_retries(robots_url, "static")
            robots = _Robots(parser=Protego.parse(response.body.decode("utf-8", "replace")))
        except FetchFailed as exc:
            if exc.reason.startswith("HTTP 4"):
                # No robots.txt (e.g. 404) means the site has no rules for bots.
                robots = _Robots(parser=None)
            else:
                # Server errors or no connection: play safe and skip this site for now.
                log.warning("Could not load %s (%s); skipping this site", robots_url, exc.reason)
                robots = _Robots(parser=None, blocked=True)
        self._robots[host] = robots
        return robots


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _retry_after_seconds(response: PageResponse) -> float | None:
    try:
        value = response.headers.get("retry-after") or response.headers.get("Retry-After")
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None  # HTTP-date form; fall back to our own backoff
