"""Database connection and the `places` table.

Works with PostgreSQL (the real thing) and SQLite (no server, handy for tests).
The embeddings teammate adds their own table that points at `places.id`; they
don't need to change this one.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    Float,
    Index,
    String,
    Text,
    Uuid,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import get_settings

# Plain JSON everywhere, but real JSONB on Postgres (so it can be indexed and queried).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class PlaceRow(Base):
    """One row per real-world place. Mirrors `app.places.models.Place`."""

    __tablename__ = "places"
    __table_args__ = (
        Index("ix_places_city_category", "city", "category"),
        Index("ix_places_wikidata_id", "wikidata_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    city: Mapped[str] = mapped_column(String(120))
    district: Mapped[str | None] = mapped_column(String(120))

    address: Mapped[str | None] = mapped_column(Text)
    directions: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    category: Mapped[str] = mapped_column(String(10))
    source_section: Mapped[str] = mapped_column(String(20))
    subsection: Mapped[str | None] = mapped_column(String(120))

    description: Mapped[str | None] = mapped_column(Text)
    opening_hours: Mapped[str | None] = mapped_column(Text)
    price_text: Mapped[str | None] = mapped_column(Text)
    price_range: Mapped[str | None] = mapped_column(String(10))
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    indoor: Mapped[bool | None] = mapped_column()

    website: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(80))
    wikidata_id: Mapped[str | None] = mapped_column(String(20))

    source: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def normalize_url(url: str) -> str:
    """`postgresql://...` -> `postgresql+psycopg://...` (we ship the psycopg 3 driver)."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(normalize_url(url or get_settings().database_url), pool_pre_ping=True)


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def reset_tables(engine: Engine) -> None:
    """Delete the `places` table and make a new empty one. This erases all places."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """A session that commits when the block finishes and rolls back on an error."""
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session, session.begin():
        yield session
