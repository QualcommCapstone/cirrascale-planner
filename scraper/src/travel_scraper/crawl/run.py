"""Run the crawl and turn what it found into a `ScrapeResult` (source "web")."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import quote

from travel_scraper.crawl.extract import ExtractedPlace
from travel_scraper.crawl.spider import PlaceSpider, build_settings
from travel_scraper.handoff import RawListing, ScrapeResult, now

SOURCE = "web"
SKIP_NO_PLACE = "page had no schema.org place data"
SKIP_FAR = "outside the city (too far from the center)"
SKIP_DUPLICATE = "same place found twice"


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    )
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def anchor(name: str) -> str:
    """A URL fragment for a place name that keeps non-ASCII names distinct ('東京タワー')."""
    text = re.sub(r"\s+", "_", unicodedata.normalize("NFKC", name).strip().casefold())
    return quote(text, safe="_-.")


def to_listing(place: ExtractedPlace, page_url: str, city: str, fetched_at: datetime) -> RawListing:
    # A page can describe several places; the anchor keeps each one's id distinct.
    return RawListing(
        source=SOURCE,
        source_url=f"{page_url}#{anchor(place.name)}",
        page_url=page_url,
        fetched_at=fetched_at,
        city=city,
        section=place.section,
        subsection=place.subsection,
        name=place.name,
        address=place.address,
        lat=place.lat,
        lng=place.lng,
        phone=place.phone,
        website=place.website,
        hours=place.hours,
        price=place.price,
        wikidata_id=place.wikidata_id,
    )


@dataclass
class CrawlCollector:
    """Receives spider output and builds the result (kept apart from Scrapy for tests)."""

    city: str
    center: tuple[float, float] | None = None
    radius_km: float = 40.0
    result: ScrapeResult = field(init=False)
    _seen: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self.result = ScrapeResult(source=SOURCE, city=self.city, started_at=now())

    def add(self, item: dict[str, Any]) -> None:
        if "no_place" in item:
            self.result.skip(SKIP_NO_PLACE)
            self._page(item["no_place"])
            return
        place: ExtractedPlace = item["place"]
        page_url: str = item["url"]
        self._page(page_url)
        if (
            self.center is not None
            and place.lat is not None
            and place.lng is not None
            and distance_km(self.center, (place.lat, place.lng)) > self.radius_km
        ):
            self.result.skip(SKIP_FAR)
            return
        listing = to_listing(place, page_url, self.city, now())
        if listing.source_url in self._seen:
            self.result.skip(SKIP_DUPLICATE)
            return
        self._seen.add(listing.source_url)
        self.result.listings.append(listing)

    def _page(self, url: str) -> None:
        if url not in self.result.pages_fetched:
            self.result.pages_fetched.append(url)

    def finish(self, stats: dict[str, Any]) -> ScrapeResult:
        forbidden = int(stats.get("robotstxt/forbidden", 0))
        if forbidden:
            self.result.skip("blocked by robots.txt", forbidden)
        errors = int(stats.get("downloader/exception_count", 0))
        if errors:
            self.result.errors.append(f"{errors} download errors (timeouts, connection failures)")
        for key, value in stats.items():
            if key.startswith("downloader/response_status_count/") and key[-3:].startswith(
                ("4", "5")
            ):
                self.result.errors.append(f"HTTP {key[-3:]} on {value} page(s)")
        self.result.finished_at = now()
        return self.result


def crawl(
    urls: list[str],
    city: str,
    *,
    user_agent: str,
    delay_s: float = 3.0,
    max_pages: int = 50,
    max_depth: int = 1,
    playwright: bool = False,
    center: tuple[float, float] | None = None,
) -> ScrapeResult:
    """Crawl and return the result. Starts a Twisted reactor, so call once per process."""
    from scrapy import signals
    from scrapy.crawler import CrawlerProcess

    collector = CrawlCollector(city=city, center=center)
    if not urls:
        return collector.finish({})
    settings = build_settings(
        user_agent=user_agent,
        delay_s=delay_s,
        max_pages=max_pages,
        max_depth=max_depth,
        playwright=playwright,
    )
    process = CrawlerProcess(settings, install_root_handler=False)
    crawler = process.create_crawler(PlaceSpider)

    def on_item(item: dict[str, Any], **_: Any) -> None:
        collector.add(item)

    crawler.signals.connect(on_item, signal=signals.item_scraped)
    process.crawl(crawler, seed_urls=urls, playwright=playwright)
    process.start()
    stats: dict[str, Any] = crawler.stats.get_stats() if crawler.stats else {}
    return collector.finish(stats)
