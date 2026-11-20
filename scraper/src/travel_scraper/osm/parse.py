"""Turn Overpass elements into `RawListing`s (pure functions, no network)."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

from travel_scraper.handoff import ListingSection, RawListing

SOURCE = "osm"
OSM_URL = "https://www.openstreetmap.org/{type}/{id}"

SKIP_NO_NAME = "no name or name:en"
SKIP_NO_COORDINATES = "no coordinates"
SKIP_DUPLICATE = "same element returned twice"

# What the place is, as a short readable label. It goes into `subsection`, which is
# what backend's tag rules read ("Museum" -> museum tags, "Ramen restaurant" -> food).
_LABELS: dict[tuple[str, str], str] = {
    ("tourism", "museum"): "Museum",
    ("tourism", "gallery"): "Art gallery",
    ("tourism", "viewpoint"): "Viewpoint",
    ("tourism", "zoo"): "Zoo",
    ("tourism", "aquarium"): "Aquarium",
    ("tourism", "theme_park"): "Theme park",
    ("tourism", "attraction"): "Attraction",
    ("tourism", "hotel"): "Hotel",
    ("tourism", "hostel"): "Hostel",
    ("tourism", "guest_house"): "Guest house",
    ("leisure", "park"): "Park",
    ("leisure", "garden"): "Garden",
    ("leisure", "nature_reserve"): "Nature reserve",
    ("amenity", "theatre"): "Theatre",
    ("amenity", "cinema"): "Cinema",
    ("amenity", "arts_centre"): "Arts centre",
    ("amenity", "marketplace"): "Market",
    ("amenity", "cafe"): "Cafe",
    ("amenity", "food_court"): "Food court",
    ("amenity", "bar"): "Bar",
    ("amenity", "pub"): "Pub",
    ("amenity", "nightclub"): "Nightclub",
    ("shop", "mall"): "Shopping mall",
    ("shop", "department_store"): "Department store",
}
_RELIGION = {
    "buddhist": "Buddhist temple",
    "shinto": "Shinto shrine",
    "christian": "Church",
    "muslim": "Mosque",
    "jewish": "Synagogue",
    "hindu": "Hindu temple",
}


def label(tags: dict[str, str]) -> str | None:
    """'Museum', 'Ramen restaurant', 'Shinto shrine', 'Historic castle', ..."""
    if tags.get("amenity") == "place_of_worship":
        text = _RELIGION.get(tags.get("religion", ""), "Place of worship")
    elif tags.get("amenity") == "restaurant":
        cuisine = _first(tags.get("cuisine"))
        text = f"{cuisine.replace('_', ' ').capitalize()} restaurant" if cuisine else "Restaurant"
    elif "historic" in tags and not any(k in tags for k in ("tourism", "leisure", "amenity")):
        kind = tags["historic"]
        text = "Historic site" if kind == "yes" else f"Historic {kind.replace('_', ' ')}"
    else:
        found = next((v for (k, val), v in _LABELS.items() if tags.get(k) == val), None)
        if found is None:
            return None
        text = found
    if tags.get("diet:vegetarian") in ("yes", "only"):
        text += " (vegetarian)"
    return text


def _first(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";")[0].strip() or None


def _address(tags: dict[str, str]) -> str | None:
    if tags.get("addr:full"):
        return tags["addr:full"].strip()
    street = " ".join(x for x in (tags.get("addr:housenumber"), tags.get("addr:street")) if x)
    parts = [street, tags.get("addr:suburb") or tags.get("addr:quarter"), tags.get("addr:postcode")]
    text = ", ".join(p for p in parts if p)
    return text or None


def _coordinates(element: dict[str, Any]) -> tuple[float | None, float | None]:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, dict) and "lat" in center and "lon" in center:
        return float(center["lat"]), float(center["lon"])
    return None, None


def _price(tags: dict[str, str]) -> str | None:
    if tags.get("fee") == "no":
        return "free"
    return tags.get("charge") or None


def richness(element: dict[str, Any]) -> tuple[int, int]:
    """Sort key for the per-section cap: Wikidata first, then the most useful tags."""
    tags = element.get("tags", {})
    useful = (
        "website",
        "opening_hours",
        "phone",
        "description",
        "addr:street",
        "addr:full",
        "cuisine",
        "name:en",
        "wikipedia",
    )
    return (0 if "wikidata" in tags else 1, -sum(key in tags for key in useful))


def to_listing(
    element: dict[str, Any], *, section: ListingSection, city: str, fetched_at: datetime
) -> RawListing | str:
    """The listing for one element, or the reason it was skipped."""
    tags: dict[str, str] = element.get("tags") or {}
    local = (tags.get("name") or "").strip()
    english = (tags.get("name:en") or "").strip()
    name = english or local
    if not name:
        return SKIP_NO_NAME
    lat, lng = _coordinates(element)
    if lat is None:
        return SKIP_NO_COORDINATES

    url = OSM_URL.format(type=element.get("type", "node"), id=element.get("id"))
    wikidata = tags.get("wikidata")
    return RawListing(
        source=SOURCE,
        source_url=url,
        page_url=url,
        fetched_at=fetched_at,
        city=city,
        section=section,
        subsection=label(tags),
        name=name,
        alt_name=local if local and local != name else None,
        address=_address(tags),
        lat=lat,
        lng=lng,
        phone=tags.get("phone") or tags.get("contact:phone"),
        email=tags.get("email") or tags.get("contact:email"),
        website=tags.get("website") or tags.get("contact:website") or tags.get("url"),
        hours=tags.get("opening_hours"),
        price=_price(tags),
        description=tags.get("description:en") or tags.get("description"),
        wikidata_id=wikidata if wikidata and wikidata.startswith("Q") else None,
    )


def parse_elements(
    elements: list[dict[str, Any]],
    *,
    section: ListingSection,
    city: str,
    fetched_at: datetime,
    max_items: int,
) -> tuple[list[RawListing], Counter[str]]:
    """Listings for one section's response, capped at `max_items` (richest first)."""
    skipped: Counter[str] = Counter()
    seen: set[tuple[str, int]] = set()
    unique: list[dict[str, Any]] = []
    for element in elements:
        key = (str(element.get("type")), int(element.get("id", 0)))
        if key in seen:
            skipped[SKIP_DUPLICATE] += 1
            continue
        seen.add(key)
        unique.append(element)

    listings: list[RawListing] = []
    for element in sorted(unique, key=richness):
        outcome = to_listing(element, section=section, city=city, fetched_at=fetched_at)
        if isinstance(outcome, str):
            skipped[outcome] += 1
            continue
        if len(listings) >= max_items:
            skipped[f"over the per-section cap of {max_items}"] += 1
            continue
        listings.append(outcome)
    return listings, skipped
