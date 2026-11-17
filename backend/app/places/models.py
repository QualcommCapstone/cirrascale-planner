"""The shared place format: one clean `Place` per real-world place.

Every source (Wikivoyage now, more later) is cleaned into this shape and stored
in the `places` table. Other teammates read it:

- Embeddings: use `Place.embedding_text()` as the text and `Place.id` as the key.
- Verifier / itinerary: `location.place_id` in docs/itinerary-schema.md is `Place.id`;
  `price_range` and `indoor` use the same values as the schema's `cost.level` and `indoor`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

# Fixed namespace so the same source link always gives the same place id.
PLACE_NAMESPACE = uuid.UUID("6f1b5f0e-3c1d-4d0a-9a53-5a4f1d7d6b21")


class Category(StrEnum):
    SEE = "see"
    DO = "do"
    EAT = "eat"
    SLEEP = "sleep"


# Same values as `cost.level` in docs/itinerary-schema.md.
PriceRange = Literal["free", "low", "mid", "high"]


def make_place_id(source: str, source_url: str) -> uuid.UUID:
    """A stable id: re-scraping the same listing never changes its id."""
    return uuid.uuid5(PLACE_NAMESPACE, f"{source}|{source_url}")


class SourceRef(BaseModel):
    """One page that told us about this place."""

    source: str = Field(min_length=1, description="e.g. 'wikivoyage'")
    url: str = Field(min_length=1)
    fetched_at: datetime

    @field_validator("fetched_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return as_utc(value)


class Place(BaseModel):
    id: uuid.UUID
    name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    district: str | None = None

    address: str | None = None
    directions: str | None = Field(
        default=None, description="'near X station' style hints that are not a street address."
    )
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)

    category: Category
    source_section: str = Field(description="The source's own type, e.g. 'buy' or 'drink'.")
    subsection: str | None = Field(default=None, description="e.g. 'Budget', 'Museums'.")

    description: str | None = None
    opening_hours: str | None = Field(default=None, description="As written. Parsed in step 3.")
    price_text: str | None = Field(default=None, description="As written, e.g. '¥1200'.")
    price_range: PriceRange | None = Field(default=None, description="Filled in step 3.")
    tags: list[str] = Field(default_factory=list, description="Interest tags. Filled in step 3.")
    indoor: bool | None = Field(default=None, description="Filled in step 3.")

    website: str | None = None
    phone: str | None = None
    wikidata_id: str | None = None

    # The main source, plus every source that mentioned this place.
    source: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    fetched_at: datetime
    sources: list[SourceRef] = Field(default_factory=list)

    @field_validator("fetched_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_validator("source_url")
    @classmethod
    def _real_link(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("source_url must be a web link")
        return value

    @model_validator(mode="after")
    def _check(self) -> Self:
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must both be set or both be empty")
        if not self.sources:
            self.sources = [
                SourceRef(source=self.source, url=self.source_url, fetched_at=self.fetched_at)
            ]
        return self

    @property
    def has_coordinates(self) -> bool:
        return self.lat is not None and self.lng is not None

    def embedding_text(self) -> str:
        """One plain-text summary of the place, meant to be fed to an embedding model."""
        where = f"{self.district}, {self.city}" if self.district else self.city
        parts = [f"{self.name} ({self.category.value}) in {where}."]
        if self.subsection:
            parts.append(f"{self.subsection}.")
        if self.description:
            parts.append(self.description)
        if self.price_range:
            parts.append(f"Price: {self.price_range}.")
        elif self.price_text:
            parts.append(f"Price: {self.price_text}.")
        if self.tags:
            parts.append("Tags: " + ", ".join(self.tags) + ".")
        return " ".join(parts)


def as_utc(value: datetime) -> datetime:
    """Treat a time with no timezone as UTC (SQLite drops timezones)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
