"""Turn raw scraped listings into clean `Place` records.

Cleaning rules (each one is covered by a test):
- Wikivoyage's six types become our four categories: see, do, eat, sleep.
  (buy -> do, drink -> eat.) The original type is kept in `source_section`
  so step 3 can still tell shopping and nightlife apart.
- Text is tidied: Unicode normalized, extra spaces and `[1]` footnote marks removed.
- "Addresses" that are really directions ("near Ueno station") move to `directions`.
- Placeholder values ("?", "n/a", "TBD") become empty.
- Coordinates must be real. (0, 0) and half-empty pairs are dropped.
- A listing with no usable name or no source link is dropped, and counted.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.places.models import Category, Place, make_place_id
from app.scraping.models import RawListing

SECTION_TO_CATEGORY: dict[str, Category] = {
    "see": Category.SEE,
    "do": Category.DO,
    "buy": Category.DO,
    "eat": Category.EAT,
    "drink": Category.EAT,
    "sleep": Category.SLEEP,
}

DROP_NO_NAME = "no usable name"
DROP_NO_SOURCE = "no source link"
DROP_UNKNOWN_TYPE = "unknown place type"
DROP_INVALID = "failed validation"

_WS = re.compile(r"\s+")
_FOOTNOTE = re.compile(r"\[\s*(?:\d+|edit|citation needed)\s*\]", re.I)
_PLACEHOLDERS = frozenset({"", "?", "??", "-", "--", "n/a", "na", "none", "unknown", "tbd", "tba"})
_DIRECTION_START = re.compile(
    r"^(located|in front of|next to|near|opposite|across|behind|inside|just |at the |"
    r"on the |a few |close to|adjacent|[\d.]+\s*(?:min|minutes?|m|km|metres?|meters?)\b)",
    re.I,
)


@dataclass
class CleanReport:
    dropped: Counter[str] = field(default_factory=Counter)

    @property
    def total_dropped(self) -> int:
        return sum(self.dropped.values())


def clean_listings(raws: Iterable[RawListing]) -> tuple[list[Place], CleanReport]:
    """Clean many listings. Bad ones are dropped and counted, never fatal."""
    report = CleanReport()
    places: list[Place] = []
    for raw in raws:
        result = clean_listing(raw)
        if isinstance(result, str):
            report.dropped[result] += 1
        else:
            places.append(result)
    return places, report


def clean_listing(raw: RawListing) -> Place | str:
    """Return the clean `Place`, or the reason this listing was dropped."""
    category = SECTION_TO_CATEGORY.get(raw.section)
    if category is None:
        return DROP_UNKNOWN_TYPE

    name = clean_name(raw.name)
    if name is None:
        return DROP_NO_NAME

    source_url = (raw.source_url or "").strip()
    if not source_url.startswith(("http://", "https://")):
        return DROP_NO_SOURCE

    address, directions = split_address(raw.address, raw.directions)
    lat, lng = clean_coordinates(raw.lat, raw.lng)

    try:
        return Place(
            id=make_place_id(raw.source, source_url),
            name=name,
            city=clean_text(raw.city) or raw.city,
            district=clean_text(raw.district),
            address=address,
            directions=directions,
            lat=lat,
            lng=lng,
            category=category,
            source_section=raw.section,
            subsection=clean_text(raw.subsection),
            description=clean_text(raw.description),
            opening_hours=clean_value(raw.hours),
            price_text=clean_value(raw.price),
            website=clean_url(raw.website),
            phone=clean_value(raw.phone),
            wikidata_id=clean_value(raw.wikidata_id),
            source=raw.source,
            source_url=source_url,
            fetched_at=raw.fetched_at,
        )
    except ValueError:
        return DROP_INVALID


# ---- small helpers -----------------------------------------------------------


def clean_text(value: str | None) -> str | None:
    """Normalize Unicode, drop footnote marks, collapse whitespace. Empty -> None."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", value)
    text = _FOOTNOTE.sub("", text)
    text = _WS.sub(" ", text).strip()
    return text or None


def clean_value(value: str | None) -> str | None:
    """Like `clean_text`, and also turns placeholders like 'n/a' into None."""
    text = clean_text(value)
    if text is None or text.lower().strip(".") in _PLACEHOLDERS:
        return None
    return text


def clean_name(value: str | None) -> str | None:
    name = clean_text(value)
    if name is None or not any(ch.isalnum() for ch in name):
        return None
    return name[:200]


def clean_url(value: str | None) -> str | None:
    url = clean_value(value)
    return url if url and url.startswith(("http://", "https://")) else None


def clean_coordinates(lat: float | None, lng: float | None) -> tuple[float | None, float | None]:
    if lat is None or lng is None:
        return None, None
    if lat == 0 and lng == 0:  # the "null island" placeholder
        return None, None
    return lat, lng


def split_address(address: str | None, directions: str | None) -> tuple[str | None, str | None]:
    """Keep real addresses in `address`; move 'near the station' hints to `directions`."""
    addr = clean_value(address)
    hint = clean_value(directions)
    if addr and _DIRECTION_START.match(addr):
        hint = hint or addr
        addr = None
    return addr, hint
