"""Read and write places in the database."""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.places.db import PlaceRow
from app.places.models import Category, Place, SourceRef

# Plain columns copied between `Place` and `PlaceRow` (`id` and `sources` are handled apart).
_FIELDS = [
    "name", "city", "district", "address", "directions", "lat", "lng",
    "category", "source_section", "subsection",
    "description", "opening_hours", "price_text", "price_range", "tags", "indoor",
    "website", "phone", "wikidata_id", "source", "source_url", "fetched_at",
]  # fmt: skip


def save_places(session: Session, places: Iterable[Place]) -> tuple[int, int]:
    """Insert new places and update ones that already exist. Returns (inserted, updated)."""
    inserted = updated = 0
    for place in places:
        row = session.get(PlaceRow, place.id)
        if row is None:
            row = PlaceRow(id=place.id)
            session.add(row)
            inserted += 1
        else:
            updated += 1
        for name in _FIELDS:
            value = getattr(place, name)
            setattr(row, name, value.value if isinstance(value, Category) else value)
        row.sources = [ref.model_dump(mode="json") for ref in place.sources]
    session.flush()
    return inserted, updated


def delete_places(session: Session, ids: Iterable[uuid.UUID]) -> int:
    id_list = list(ids)
    if not id_list:
        return 0
    session.execute(delete(PlaceRow).where(PlaceRow.id.in_(id_list)))
    return len(id_list)


def to_place(row: PlaceRow) -> Place:
    return Place(
        id=row.id,
        sources=[SourceRef.model_validate(ref) for ref in row.sources or []],
        **{name: getattr(row, name) for name in _FIELDS},
    )


def get_place(session: Session, place_id: uuid.UUID) -> Place | None:
    row = session.get(PlaceRow, place_id)
    return to_place(row) if row else None


def load_city(session: Session, city: str) -> list[Place]:
    """All places of a city, oldest first (so ids stay stable when merging)."""
    stmt = (
        select(PlaceRow)
        .where(func.lower(PlaceRow.city) == city.lower())
        .order_by(PlaceRow.created_at, PlaceRow.id)
    )
    return [to_place(row) for row in session.scalars(stmt)]


def search_places(
    session: Session,
    *,
    city: str | None = None,
    category: Category | None = None,
    text: str | None = None,
    limit: int | None = None,
) -> list[Place]:
    stmt = select(PlaceRow).order_by(PlaceRow.city, PlaceRow.category, PlaceRow.name)
    if city:
        stmt = stmt.where(func.lower(PlaceRow.city) == city.lower())
    if category:
        stmt = stmt.where(PlaceRow.category == category.value)
    if text:
        stmt = stmt.where(PlaceRow.name.ilike(f"%{text}%"))
    if limit:
        stmt = stmt.limit(limit)
    return [to_place(row) for row in session.scalars(stmt)]


def count_by_city_and_category(session: Session) -> list[tuple[str, str, int]]:
    stmt = (
        select(PlaceRow.city, PlaceRow.category, func.count())
        .group_by(PlaceRow.city, PlaceRow.category)
        .order_by(PlaceRow.city, PlaceRow.category)
    )
    return [(city, category, count) for city, category, count in session.execute(stmt)]
