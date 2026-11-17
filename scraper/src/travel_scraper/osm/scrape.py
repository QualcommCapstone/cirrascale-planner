"""Run the Overpass queries for a city and collect a `ScrapeResult`."""

from __future__ import annotations

import logging
from typing import Any

from travel_scraper.handoff import SECTIONS, ListingSection, ScrapeResult, now
from travel_scraper.http import ApiClient, ApiFailed, RetryableResponse
from travel_scraper.osm.parse import SOURCE, parse_elements
from travel_scraper.osm.query import build_query

log = logging.getLogger(__name__)

# Overpass reports a failed or cut-short query in `remark`, with HTTP 200.
_BAD_REMARK = ("runtime error", "timed out", "out of memory", "query run out")


def check_overpass(body: Any) -> None:
    """Raise if the response is partial (a 200 that is really an error)."""
    if not isinstance(body, dict) or "elements" not in body:
        raise RetryableResponse("Overpass response has no 'elements'")
    remark = str(body.get("remark") or "").lower()
    if any(marker in remark for marker in _BAD_REMARK):
        raise RetryableResponse(f"Overpass partial result: {body['remark']}")


def scrape_osm(
    city: str,
    center: tuple[float, float],
    client: ApiClient,
    *,
    overpass_url: str,
    radius_km: float = 15.0,
    max_per_section: int = 300,
    sections: tuple[ListingSection, ...] = SECTIONS,
) -> ScrapeResult:
    """One query per section. A failed section is recorded in `errors` and contributes
    nothing (never partial data); the other sections still run.
    """
    result = ScrapeResult(source=SOURCE, city=city, started_at=now())
    # Ask the server for more than the cap so the richest can be picked locally.
    server_limit = max_per_section * 4
    for section in sections:
        query = build_query(section, center, radius_km, limit=server_limit)
        try:
            body = client.post_json(overpass_url, {"data": query}, check=check_overpass)
        except ApiFailed as exc:
            result.errors.append(f"osm {section}: {exc.reason}")
            log.warning("Overpass %s failed: %s", section, exc.reason)
            continue
        listings, skipped = parse_elements(
            body["elements"],
            section=section,
            city=city,
            fetched_at=now(),
            max_items=max_per_section,
        )
        result.pages_fetched.append(f"{overpass_url}#{section}")
        result.listings.extend(listings)
        for reason, count in skipped.items():
            result.skip(reason, count)
        log.info("osm %s: %d listings", section, len(listings))
    result.finished_at = now()
    return result
