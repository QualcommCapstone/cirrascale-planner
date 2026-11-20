"""Small builders for test data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.places.models import Category, Place, make_place_id
from app.scraping.models import RawListing

WHEN = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


def raw(name: str = "Fire Museum", **kw: Any) -> RawListing:
    values: dict[str, Any] = {
        "source": "wikivoyage",
        "source_url": f"https://en.wikivoyage.org/wiki/Testville#{name.replace(' ', '_')}",
        "page_url": "https://en.wikivoyage.org/wiki/Testville",
        "fetched_at": WHEN,
        "city": "Testville",
        "section": "see",
        "name": name,
    }
    values.update(kw)
    return RawListing(**values)


def place(name: str = "Fire Museum", **kw: Any) -> Place:
    source = kw.pop("source", "wikivoyage")
    url = kw.pop("source_url", f"https://example.org/{source}/{name.replace(' ', '_')}")
    values: dict[str, Any] = {
        "id": make_place_id(source, url),
        "name": name,
        "city": "Testville",
        "category": Category.SEE,
        "source_section": "see",
        "source": source,
        "source_url": url,
        "fetched_at": WHEN,
    }
    values.update(kw)
    return Place(**values)
