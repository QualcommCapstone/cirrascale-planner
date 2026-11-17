"""The raw handoff format: what every source here writes and `backend/` reads.

These mirror `backend/app/scraping/models.py` (`RawListing`, `ScrapeResult`) field for
field, so `uv run python -m app.places ingest <file>` in `backend/` accepts our files
unchanged. `backend/` can't be imported from here (it isn't a package and its top-level
name `app` clashes with apps/api), so the shape is copied, and
`tests/test_integration.py` checks it against the real thing.
"""

from __future__ import annotations

import re
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Wikivoyage's listing types; backend's clean step maps them onto see/do/eat/sleep.
ListingSection = Literal["see", "do", "buy", "eat", "drink", "sleep"]
SECTIONS: tuple[ListingSection, ...] = ("see", "do", "buy", "eat", "drink", "sleep")


class RawListing(BaseModel):
    source: str
    source_url: str
    page_url: str
    fetched_at: datetime

    city: str
    district: str | None = None
    section: ListingSection
    subsection: str | None = None

    name: str = Field(min_length=1)
    alt_name: str | None = None
    address: str | None = None
    directions: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    hours: str | None = None
    price: str | None = None
    description: str | None = None
    wikidata_id: str | None = None
    last_edit: str | None = None


class ScrapeResult(BaseModel):
    source: str
    city: str
    started_at: datetime
    finished_at: datetime | None = None
    pages_fetched: list[str] = Field(default_factory=list)
    listings: list[RawListing] = Field(default_factory=list)
    skipped: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)

    def skip(self, reason: str, count: int = 1) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + count


def now() -> datetime:
    return datetime.now(UTC)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "city"


def write_result(result: ScrapeResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path


def read_result(path: Path) -> ScrapeResult:
    return ScrapeResult.model_validate_json(path.read_text(encoding="utf-8"))


def raw_path(raw_dir: Path, city: str, source: str | None = None) -> Path:
    """`tokyo.json` for Wikivoyage (backend's own name), `tokyo-<source>.json` otherwise."""
    suffix = "" if source in (None, "wikivoyage") else f"-{source}"
    return raw_dir / f"{slug(city)}{suffix}.json"


def median_center(result: ScrapeResult) -> tuple[float, float] | None:
    """The city's rough center: the median of the listings' coordinates."""
    points = [(x.lat, x.lng) for x in result.listings if x.lat is not None and x.lng is not None]
    if not points:
        return None
    return statistics.median(p[0] for p in points), statistics.median(p[1] for p in points)
