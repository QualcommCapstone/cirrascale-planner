"""Overpass QL queries, one per section, with the quality filters inside the query.

Filtering on the server means we never download (and the shared public Overpass
instance never has to send) the thousands of minor places we would throw away: a big
city has tens of thousands of restaurants and pocket parks in OSM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from travel_scraper.handoff import ListingSection

# Keep an element only if it has a `name`. (A key regex like `~"^name(:en)?$"` also
# catches the rare name:en-only element, but makes every query much slower.)
HAS_NAME = '["name"]'


@dataclass(frozen=True)
class Selector:
    """One Overpass statement: a tag filter plus required extra keys."""

    tags: str
    requires: tuple[str, ...] = ()

    def statement(self) -> str:
        extra = "".join(f'["{key}"]' for key in self.requires)
        return f"  nwr{self.tags}{extra}{HAS_NAME};"


def _any(*keys: str) -> list[tuple[str, ...]]:
    return [(key,) for key in keys]


# Each section: (tag filter, list of alternative "requires" sets). An element matches
# if it has the tags AND every key of at least one alternative.
SECTION_RULES: dict[ListingSection, list[tuple[str, list[tuple[str, ...]]]]] = {
    "see": [
        ('["tourism"~"^(attraction|museum|gallery|viewpoint|zoo|aquarium|theme_park)$"]', [()]),
        ('["historic"]', [("wikidata",)]),
        ('["amenity"="place_of_worship"]', [("wikidata",)]),
    ],
    "do": [
        ('["leisure"~"^(park|garden|nature_reserve)$"]', _any("wikidata", "website")),
        ('["amenity"~"^(theatre|cinema|arts_centre)$"]', _any("wikidata", "website")),
    ],
    "buy": [
        ('["shop"~"^(mall|department_store)$"]', [()]),
        ('["amenity"="marketplace"]', [()]),
    ],
    "eat": [
        (
            '["amenity"~"^(restaurant|cafe|food_court)$"]',
            [("wikidata",), ("website", "opening_hours")],
        ),
    ],
    "drink": [
        ('["amenity"~"^(bar|pub|nightclub)$"]', [("wikidata",), ("website", "opening_hours")]),
    ],
    "sleep": [
        ('["tourism"~"^(hotel|hostel|guest_house)$"]', _any("wikidata", "website")),
    ],
}


def selectors(section: ListingSection) -> list[Selector]:
    return [
        Selector(tags, requires)
        for tags, alternatives in SECTION_RULES[section]
        for requires in alternatives
    ]


# Server-side time limit for one query. The client waits longer than this (see cli.py),
# so we never disconnect and retry while the server is still working on the first try:
# that would hold two of our slots and earn a 429.
QUERY_TIMEOUT_S = 90


def bbox(center: tuple[float, float], radius_km: float) -> tuple[float, float, float, float]:
    """(south, west, north, east) of the square around `center`.

    A bounding box is much cheaper for Overpass than `around:` (a radius test per element).
    """
    lat, lng = center
    dlat = radius_km / 111.32
    dlng = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return (
        max(-90.0, lat - dlat),
        max(-180.0, lng - dlng),
        min(90.0, lat + dlat),
        min(180.0, lng + dlng),
    )


def build_query(
    section: ListingSection,
    center: tuple[float, float],
    radius_km: float,
    *,
    limit: int,
    timeout_s: int = QUERY_TIMEOUT_S,
) -> str:
    """Overpass QL for one section in the box around `center`; `limit` caps the reply."""
    s, w, n, e = bbox(center, radius_km)
    body = "\n".join(sel.statement() for sel in selectors(section))
    return (
        f"[out:json][timeout:{timeout_s}][bbox:{s:.5f},{w:.5f},{n:.5f},{e:.5f}];\n"
        f"(\n{body}\n);\nout center tags {limit};"
    )
