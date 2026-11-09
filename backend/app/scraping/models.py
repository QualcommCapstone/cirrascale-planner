"""Raw scraped records.

A `RawListing` is one place exactly as a source described it, before any
cleaning or merging. The next step (clean format + database) turns these into
our shared `Place` format. Keeping the raw text means we can always re-clean
later without scraping again.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Wikivoyage's own listing types. The clean step maps these onto our
# see/do/eat/sleep categories (e.g. buy -> do, drink -> eat).
ListingSection = Literal["see", "do", "buy", "eat", "drink", "sleep"]


class RawListing(BaseModel):
    source: str = Field(description="Where this came from, e.g. 'wikivoyage'.")
    source_url: str = Field(description="Link to this exact listing (page URL + #anchor).")
    page_url: str
    fetched_at: datetime

    city: str
    district: str | None = None
    section: ListingSection
    subsection: str | None = Field(
        default=None, description="Heading under the section, e.g. 'Budget' or 'Museums'."
    )

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
    last_edit: str | None = Field(default=None, description="Source's own 'updated' note.")


class ScrapeResult(BaseModel):
    """Everything one scrape run produced, including what went wrong."""

    source: str
    city: str
    started_at: datetime
    finished_at: datetime | None = None
    pages_fetched: list[str] = Field(default_factory=list)
    listings: list[RawListing] = Field(default_factory=list)
    skipped: dict[str, int] = Field(
        default_factory=dict, description="Why listings were left out -> how many."
    )
    errors: list[str] = Field(default_factory=list)
