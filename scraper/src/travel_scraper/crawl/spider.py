"""The place spider: start from eligible discovered URLs, extract, follow place links."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import urlsplit

import scrapy
from scrapy.http import Response

from travel_scraper.crawl.extract import extract_places, looks_client_rendered

# Same-domain links worth following: listing pages, place pages, pagination.
FOLLOW = re.compile(
    r"/(attractions?|sights?|spots?|see|eat|museums?|restaurants?|dining|things-to-do|"
    r"activities|places?|venues?|shops?|shopping|nightlife|bars?|parks?|temples?|shrines?)"
    r"(/|$|\?)|[?&]page=\d+",
    re.I,
)


def build_settings(
    *,
    user_agent: str,
    delay_s: float,
    max_pages: int,
    max_depth: int,
    playwright: bool,
) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "USER_AGENT": user_agent,
        "ROBOTSTXT_OBEY": True,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": delay_s,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "CONCURRENT_REQUESTS": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "DOWNLOAD_DELAY": delay_s,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 2,
        "DEPTH_LIMIT": max_depth,
        "CLOSESPIDER_PAGECOUNT": max_pages,
        "COOKIES_ENABLED": False,
        "TELNETCONSOLE_ENABLED": False,
        "LOG_LEVEL": "WARNING",
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
    }
    if playwright:
        settings["DOWNLOAD_HANDLERS"] = {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        }
        settings["TWISTED_REACTOR"] = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
    return settings


def site_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


class PlaceSpider(scrapy.Spider):
    name = "places"

    def __init__(
        self, seed_urls: list[str] | None = None, playwright: bool = False, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.seed_urls = list(seed_urls or [])
        self.playwright = playwright
        # Sites, without `www.`; subdomains count as the same site (like Scrapy's
        # OffsiteMiddleware), so www.example.com and example.com match either way.
        self.allowed_domains = sorted({site_of(u) for u in self.seed_urls})

    def same_site(self, url: str) -> bool:
        host = site_of(url)
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    async def start(self) -> AsyncIterator[scrapy.Request]:
        for url in self.seed_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response: Response, **_: Any) -> Iterator[Any]:
        html = response.text if hasattr(response, "text") else ""
        places = extract_places(html, response.url)
        rendered = bool(response.meta.get("playwright"))
        if not places and self.playwright and not rendered and looks_client_rendered(html):
            yield scrapy.Request(
                response.url,
                callback=self.parse,
                meta={**response.meta, "playwright": True},
                dont_filter=True,
            )
            return
        for place in places:
            yield {"place": place, "url": response.url}
        if not places:
            yield {"no_place": response.url}
        for href in response.css("a::attr(href)").getall():
            url = response.urljoin(href)
            if self.same_site(url) and FOLLOW.search(url):
                yield response.follow(url, callback=self.parse)
