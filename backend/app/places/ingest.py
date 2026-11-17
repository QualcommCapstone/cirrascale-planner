"""The pipeline: raw scraped listings -> clean places -> no duplicates -> database.

    clean_listings()  ->  dedupe(existing places + new places)  ->  save

Existing places of the city are loaded first and put at the front of the list,
so a place keeps its id when a new scrape or a second source describes it again.
Running the same ingest twice changes nothing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.places import repo
from app.places.clean import clean_listings
from app.places.dedupe import MergeNote, Rules, dedupe
from app.places.models import Place
from app.scraping.models import RawListing


@dataclass
class IngestReport:
    raw: int = 0
    cleaned: int = 0
    dropped: Counter[str] = field(default_factory=Counter)
    duplicates_removed: int = 0
    refreshed: int = 0
    merges: list[MergeNote] = field(default_factory=list)
    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    per_city: Counter[str] = field(default_factory=Counter)  # places in each city afterwards
    saved: bool = False


def ingest(
    listings: list[RawListing],
    session: Session | None,
    *,
    rules: Rules | None = None,
) -> IngestReport:
    """Run the pipeline. With `session=None` nothing is read from or written to a database
    (a "dry run": clean and dedupe the listings against each other only).
    """
    report = IngestReport(raw=len(listings))
    places, clean_report = clean_listings(listings)
    report.cleaned = len(places)
    report.dropped = clean_report.dropped

    by_city: dict[str, list[Place]] = {}
    for place in places:
        by_city.setdefault(place.city, []).append(place)

    for city, new_places in by_city.items():
        existing = repo.load_city(session, city) if session is not None else []
        result = dedupe(existing + new_places, rules)
        report.duplicates_removed += result.duplicates_removed
        report.refreshed += result.refreshed
        report.merges.extend(result.merges)
        report.per_city[city] = len(result.places)

        if session is not None:
            kept_ids = {p.id for p in result.places}
            report.deleted += repo.delete_places(
                session, [p.id for p in existing if p.id not in kept_ids]
            )
            inserted, updated = repo.save_places(session, result.places)
            report.inserted += inserted
            report.updated += updated
            report.saved = True
    return report
