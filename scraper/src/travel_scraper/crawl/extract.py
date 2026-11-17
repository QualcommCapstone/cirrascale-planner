"""Extract places from a web page (pure functions over HTML; no network).

Order of evidence:
1. JSON-LD (`<script type="application/ld+json">`) with a schema.org place type.
2. Microdata (`itemscope itemtype="https://schema.org/Restaurant"`) as the fallback.

A page with neither gives nothing: without a schema.org type we can't tell a museum
from a blog post, and guessing would put made-up places in the data.

Facts only: name, address, coordinates, hours, price, phone, website, Wikidata ID.
Descriptions are **not** copied from crawled sites (their text is copyrighted and this
repo is public); `source_url` links back to the page instead.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, replace
from typing import Any

from parsel import Selector

from travel_scraper.handoff import ListingSection

# schema.org type -> (section, readable label for `subsection`).
PLACE_TYPES: dict[str, tuple[ListingSection, str]] = {
    "TouristAttraction": ("see", "Attraction"),
    "Museum": ("see", "Museum"),
    "ArtGallery": ("see", "Art gallery"),
    "LandmarksOrHistoricalBuildings": ("see", "Historic landmark"),
    "PlaceOfWorship": ("see", "Place of worship"),
    "BuddhistTemple": ("see", "Buddhist temple"),
    "Church": ("see", "Church"),
    "Mosque": ("see", "Mosque"),
    "Zoo": ("see", "Zoo"),
    "Aquarium": ("see", "Aquarium"),
    "Park": ("do", "Park"),
    "AmusementPark": ("do", "Amusement park"),
    "MovieTheater": ("do", "Cinema"),
    "PerformingArtsTheater": ("do", "Theatre"),
    "ShoppingCenter": ("buy", "Shopping mall"),
    "DepartmentStore": ("buy", "Department store"),
    "Restaurant": ("eat", "Restaurant"),
    "FoodEstablishment": ("eat", "Restaurant"),
    "FastFoodRestaurant": ("eat", "Fast food restaurant"),
    "CafeOrCoffeeShop": ("eat", "Cafe"),
    "Bakery": ("eat", "Bakery"),
    "BarOrPub": ("drink", "Bar"),
    "NightClub": ("drink", "Nightclub"),
    "Brewery": ("drink", "Brewery"),
    "Winery": ("drink", "Winery"),
    "Hotel": ("sleep", "Hotel"),
    "LodgingBusiness": ("sleep", "Lodging"),
    "Hostel": ("sleep", "Hostel"),
    "Resort": ("sleep", "Resort"),
    "BedAndBreakfast": ("sleep", "Bed and breakfast"),
}
_DAYS = {
    "monday": "Mo", "tuesday": "Tu", "wednesday": "We", "thursday": "Th",
    "friday": "Fr", "saturday": "Sa", "sunday": "Su",
}  # fmt: skip
_QID = re.compile(r"wikidata\.org/(?:wiki|entity)/(Q\d+)")
_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class ExtractedPlace:
    name: str
    section: ListingSection
    subsection: str
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    hours: str | None = None
    price: str | None = None
    phone: str | None = None
    website: str | None = None
    wikidata_id: str | None = None
    method: str = "json-ld"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = next((v for v in value if v), None)
        if value is None:
            return None
    if isinstance(value, dict):
        value = value.get("@value") or value.get("name")
    text = _WS.sub(" ", str(value)).strip()
    return text or None


def _types(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type")
    values = raw if isinstance(raw, list) else [raw]
    return [str(v).rsplit("/", 1)[-1] for v in values if v]


def place_type(types: list[str]) -> tuple[ListingSection, str] | None:
    for t in types:
        if t in PLACE_TYPES:
            return PLACE_TYPES[t]
    return None


def _address(value: Any) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        parts = [
            _text(value.get(k))
            for k in ("streetAddress", "addressLocality", "addressRegion", "postalCode")
        ]
        text = ", ".join(p for p in parts if p)
        return text or None
    return _text(value)


def _number(value: Any, limit: float) -> float | None:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if abs(number) <= limit and number == number else None


def _geo(node: dict[str, Any]) -> tuple[float | None, float | None]:
    geo = node.get("geo")
    if isinstance(geo, list):
        geo = geo[0] if geo else None
    if not isinstance(geo, dict):
        return None, None
    lat, lng = _number(geo.get("latitude"), 90), _number(geo.get("longitude"), 180)
    if lat is None or lng is None or (lat == 0 and lng == 0):
        return None, None
    return lat, lng


def _day(value: Any) -> str | None:
    name = str(value).rsplit("/", 1)[-1].lower()
    return _DAYS.get(name)


def opening_hours(node: dict[str, Any]) -> str | None:
    """`openingHours` as written, or `openingHoursSpecification` as 'Mo 09:00-17:00; ...'."""
    raw = node.get("openingHours")
    if raw:
        values = raw if isinstance(raw, list) else [raw]
        text = "; ".join(t for t in (_text(v) for v in values) if t)
        if text:
            return text
    specs = node.get("openingHoursSpecification")
    if not specs:
        return None
    parts: list[str] = []
    for spec in specs if isinstance(specs, list) else [specs]:
        if not isinstance(spec, dict):
            continue
        opens, closes = _text(spec.get("opens")), _text(spec.get("closes"))
        days_raw = spec.get("dayOfWeek")
        days = [
            d
            for d in (_day(x) for x in (days_raw if isinstance(days_raw, list) else [days_raw]))
            if d
        ]
        if opens and closes and days:
            parts.append(f"{','.join(days)} {opens[:5]}-{closes[:5]}")
    return "; ".join(parts) or None


def _wikidata(node: dict[str, Any]) -> str | None:
    same = node.get("sameAs")
    for value in same if isinstance(same, list) else [same]:
        match = _QID.search(str(value or ""))
        if match:
            return match.group(1)
    return None


def _label(node: dict[str, Any], base: str) -> str:
    cuisine = _text(node.get("servesCuisine"))
    if cuisine and base in ("Restaurant", "Fast food restaurant"):
        return f"{cuisine.capitalize()} restaurant"
    return base


def _from_node(node: dict[str, Any], page_url: str) -> ExtractedPlace | None:
    kind = place_type(_types(node))
    name = _text(node.get("name"))
    if kind is None or not name:
        return None
    section, base = kind
    lat, lng = _geo(node)
    website = _text(node.get("url"))
    return ExtractedPlace(
        name=name[:200],
        section=section,
        subsection=_label(node, base),
        address=_address(node.get("address")),
        lat=lat,
        lng=lng,
        hours=opening_hours(node),
        price=_text(node.get("priceRange")),
        phone=_text(node.get("telephone")),
        website=website if website and website.startswith(("http://", "https://")) else page_url,
        wikidata_id=_wikidata(node),
    )


def _walk(data: Any) -> Iterator[dict[str, Any]]:
    """Every object in a JSON-LD document, including inside `@graph` and lists."""
    if isinstance(data, list):
        for item in data:
            yield from _walk(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "itemListElement", "item", "mainEntity", "containsPlace"):
            if key in data:
                yield from _walk(data[key])


def jsonld_blocks(html: str) -> list[Any]:
    """Parsed JSON-LD documents. Broken blocks are skipped."""
    blocks: list[Any] = []
    for raw in Selector(text=html).css('script[type="application/ld+json"]::text').getall():
        try:
            blocks.append(json.loads(raw.strip()))
        except ValueError:
            continue
    return blocks


def from_jsonld(html: str, page_url: str) -> list[ExtractedPlace]:
    places: list[ExtractedPlace] = []
    for block in jsonld_blocks(html):
        for node in _walk(block):
            place = _from_node(node, page_url)
            if place is not None and place not in places:
                places.append(place)
    return places


def _own_props(scope: Any) -> dict[str, Any]:
    """`itemprop` elements that belong to this itemscope itself, first one per name.

    A property inside a nested itemscope (a Review's author `name`, an address's parts)
    belongs to that nested item, not to this one.
    """
    owned: dict[str, Any] = {}
    root = scope.root
    for el in root.iterdescendants():
        prop = el.get("itemprop") if hasattr(el, "get") else None
        if not prop or prop in owned:
            continue
        parent = el.getparent()
        while parent is not None and parent is not root and parent.get("itemscope") is None:
            parent = parent.getparent()
        if parent is root:
            owned[prop] = el
    return owned


def _prop_value(el: Any) -> str | None:
    value = el.get("content") or el.get("href") or "".join(el.itertext())
    text = _WS.sub(" ", value or "").strip()
    return text or None


def from_microdata(html: str, page_url: str) -> list[ExtractedPlace]:
    places: list[ExtractedPlace] = []
    for scope in Selector(text=html).css("[itemscope][itemtype]"):
        node: dict[str, Any] = {"@type": scope.attrib.get("itemtype", "")}
        props = _own_props(scope)
        for prop in ("name", "telephone", "priceRange", "openingHours", "servesCuisine", "url"):
            if prop in props and (value := _prop_value(props[prop])):
                node[prop] = value
        if "address" in props:
            node["address"] = _prop_value(props["address"])
        geo = props.get("geo")
        if geo is not None:
            inner = _own_props(Selector(root=geo))
            lat, lng = inner.get("latitude"), inner.get("longitude")
            if lat is not None and lng is not None:
                node["geo"] = {"latitude": _prop_value(lat), "longitude": _prop_value(lng)}
        found = _from_node(node, page_url)
        if found is None:
            continue
        place = replace(found, method="microdata")
        if place not in places:
            places.append(place)
    return places


def extract_places(html: str, page_url: str) -> list[ExtractedPlace]:
    return from_jsonld(html, page_url) or from_microdata(html, page_url)


def looks_client_rendered(html: str) -> bool:
    """No structured data and almost no visible text: probably built by JavaScript."""
    if jsonld_blocks(html):
        return False
    sel = Selector(text=html)
    if sel.css("[itemscope][itemtype]"):
        return False
    text = " ".join(sel.css("body *:not(script):not(style)::text").getall())
    return len(_WS.sub(" ", text).strip()) < 200
