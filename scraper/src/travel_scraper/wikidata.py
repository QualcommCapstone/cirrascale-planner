"""Fill missing coordinates from Wikidata (P625). Data license: CC0 1.0.

The backend contract requires lat/lng, so every Wikivoyage listing that has a
Wikidata ID but no map marker is a place we'd otherwise have to drop.

Uses the official API (`wbgetentities`, 50 IDs per request) through `ApiClient`:
serial requests, honest User-Agent, and `maxlag` so we back off when Wikidata is busy.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from travel_scraper.handoff import RawListing, ScrapeResult
from travel_scraper.http import ApiClient, ApiFailed, RetryableResponse

BATCH = 50
_QID = re.compile(r"^Q\d+$")


def check_wikidata(body: Any) -> None:
    """A `maxlag` error comes back as HTTP 200; treat it as a retryable failure."""
    if not isinstance(body, dict):
        raise RetryableResponse("Wikidata response is not an object")
    error = body.get("error")
    if isinstance(error, dict):
        if error.get("code") == "maxlag":
            lag = error.get("lag")
            raise RetryableResponse("Wikidata maxlag", retry_after=float(lag) if lag else 5.0)
        # Anything else (bad ids, bad params) won't fix itself: fail the batch now.
        raise ApiFailed("wikidata", f"Wikidata error: {error.get('code')}")
    if "entities" not in body:
        raise RetryableResponse("Wikidata response has no 'entities'")


def coordinates(entity: dict[str, Any]) -> tuple[float, float] | None:
    """The first valid P625 (coordinate location) of an entity, or None."""
    for claim in entity.get("claims", {}).get("P625", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict):
            continue
        lat, lng = value.get("latitude"), value.get("longitude")
        if not (isinstance(lat, int | float) and isinstance(lng, int | float)):
            continue
        if -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0):
            return float(lat), float(lng)
    return None


def needs_coordinates(listing: RawListing) -> bool:
    return (listing.lat is None or listing.lng is None) and bool(
        listing.wikidata_id and _QID.match(listing.wikidata_id)
    )


def _batches(ids: list[str], size: int = BATCH) -> Iterable[list[str]]:
    for start in range(0, len(ids), size):
        yield ids[start : start + size]


@dataclass
class FillReport:
    candidates: int = 0
    filled: int = 0
    not_found: int = 0
    failed_batches: int = 0


def lookup(client: ApiClient, ids: list[str], *, url: str) -> dict[str, tuple[float, float]]:
    """Coordinates by Wikidata ID. A failed batch raises `ApiFailed`."""
    body = client.get_json(
        url,
        params={
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "claims",
            "format": "json",
            "maxlag": "5",
        },
        check=check_wikidata,
    )
    found: dict[str, tuple[float, float]] = {}
    for qid, entity in body["entities"].items():
        if isinstance(entity, dict) and "missing" not in entity:
            point = coordinates(entity)
            if point is not None:
                found[qid] = point
                # A merged item comes back under its new id; map it to the id we asked for.
                redirect = entity.get("redirects")
                if isinstance(redirect, dict) and redirect.get("from"):
                    found[str(redirect["from"])] = point
    return found


def fill_coordinates(result: ScrapeResult, client: ApiClient, *, url: str) -> FillReport:
    """Fill lat/lng in place for listings with a Wikidata ID and no coordinates."""
    report = FillReport()
    todo = [x for x in result.listings if needs_coordinates(x)]
    report.candidates = len(todo)
    ids = sorted({x.wikidata_id for x in todo if x.wikidata_id})
    found: dict[str, tuple[float, float]] = {}
    for batch in _batches(ids):
        try:
            found.update(lookup(client, batch, url=url))
        except ApiFailed as exc:
            report.failed_batches += 1
            result.errors.append(f"wikidata: {exc.reason}")
    for listing in todo:
        point = found.get(listing.wikidata_id or "")
        if point is None:
            report.not_found += 1
            continue
        listing.lat, listing.lng = point
        report.filled += 1
    return report
