"""Place record — the normalized unit the scraper produces (JSONL), the vector
store holds, and retrieval returns. Shared by ingestion and the RAG service.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.trip import Category


class Place(BaseModel):
    """A canonical place. Mirrors the JSONL ingestion contract (docs/api-contract.md)."""

    id: str                      # stable, source-derived id
    name: str
    description: str = ""
    city: str
    country: str
    category: Category
    lat: float
    lng: float
    address: str | None = None
    source_url: str | None = None
    source_attribution: str | None = None
    collected_at: datetime | None = None
    price_level: str | None = None       # "free" | "$" | "$$" | "$$$"
    opening_hours: str | None = None
    license: str | None = None

    def embedding_text(self) -> str:
        """Canonical text used to embed this place. Stable across re-ingestion so
        the same place always maps to the same vector for a given model."""
        parts = [self.name, self.city, self.country, self.category, self.description]
        return " — ".join(p for p in parts if p)


class SearchResult(BaseModel):
    place: Place
    score: float


class SearchFilters(BaseModel):
    city: str | None = None
    country: str | None = None
    categories: list[Category] = Field(default_factory=list)
