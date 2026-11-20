"""Export places as JSONL for the FastAPI ingestion CLI (PR #10, `apps/api`).

    uv run python -m app.places.export --city Tokyo --country Japan
    uv run python -m app.places.export --city Tokyo --country Japan --out data/export/tokyo.jsonl

The backend's contract is `apps/api/app/schemas/place.py`. That model lives in a
different Python environment (and its package is also called `app`), so it can't be
imported here. `ContractPlace` below copies its field rules; the integration test in
`scraper/tests` checks the output against the real model by running its ingest CLI.

Run after `ingest` and `enrich`: categories are worked out from the tags `enrich` sets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from app.places import repo
from app.places.db import create_tables, make_engine, session_scope
from app.places.models import Category, Place

ContractCategory = Literal["sight", "food", "nature", "culture", "nightlife", "shopping"]


class ContractPlace(BaseModel):
    """Field rules of `apps/api/app/schemas/place.py::Place`. Keep in sync with it."""

    id: str
    name: str
    description: str = ""
    city: str
    country: str
    category: ContractCategory
    lat: float
    lng: float
    address: str | None = None
    source_url: str | None = None
    source_attribution: str | None = None
    collected_at: datetime | None = None
    price_level: str | None = None  # "free" | "$" | "$$" | "$$$"
    opening_hours: str | None = None
    license: str | None = None


PRICE_LEVEL = {"free": "free", "low": "$", "mid": "$$", "high": "$$$"}

ATTRIBUTION = {
    "wikivoyage": "Wikivoyage contributors",
    "osm": "© OpenStreetMap contributors",
}
LICENSE = {
    "wikivoyage": "CC BY-SA 4.0",
    "osm": "ODbL 1.0",
}
UNKNOWN_LICENSE = "see source"

NATURE_TAGS = frozenset({"nature", "outdoors", "hiking", "beach", "views"})
CULTURE_TAGS = frozenset({"museum", "art", "history", "culture", "religious", "architecture"})

SKIP_NO_COORDINATES = "no coordinates (the contract requires lat/lng)"
SKIP_LODGING = "lodging (the contract has no category for it)"


def contract_category(place: Place) -> ContractCategory | None:
    """Map our category/section/tags onto the contract's six. None = not exportable."""
    if place.source_section == "drink":
        return "nightlife"
    if place.source_section == "buy":
        return "shopping"
    if place.category is Category.EAT:
        return "food"
    if place.category is Category.SLEEP:
        return None
    tags = set(place.tags)
    if tags & NATURE_TAGS:
        return "nature"
    if tags & CULTURE_TAGS:
        return "culture"
    if "nightlife" in tags:
        return "nightlife"
    if "shopping" in tags:
        return "shopping"
    return "sight"


def _source_names(place: Place) -> list[str]:
    names: list[str] = []
    for name in [place.source, *(ref.source for ref in place.sources)]:
        if name not in names:
            names.append(name)
    return names


def _attribution(place: Place) -> str:
    parts: list[str] = []
    for ref in place.sources or []:
        label = ATTRIBUTION.get(ref.source)
        if label is None:  # a crawled website: credit its host
            label = urlsplit(ref.url).netloc.removeprefix("www.") or ref.source
        if label not in parts:
            parts.append(label)
    return "; ".join(parts) or ATTRIBUTION.get(place.source, place.source)


def _license(place: Place) -> str:
    parts: list[str] = []
    for name in _source_names(place):
        value = LICENSE.get(name, UNKNOWN_LICENSE)
        if value not in parts:
            parts.append(value)
    return "; ".join(parts)


def to_contract(place: Place, country: str) -> ContractPlace | str:
    """The contract record for a place, or the reason it can't be exported."""
    category = contract_category(place)
    if category is None:
        return SKIP_LODGING
    if place.lat is None or place.lng is None:
        return SKIP_NO_COORDINATES
    return ContractPlace(
        id=str(place.id),
        name=place.name,
        description=place.description or "",
        city=place.city,
        country=country,
        category=category,
        lat=place.lat,
        lng=place.lng,
        address=place.address,
        source_url=place.source_url,
        source_attribution=_attribution(place),
        collected_at=place.fetched_at,
        price_level=PRICE_LEVEL.get(place.price_range) if place.price_range else None,
        opening_hours=place.opening_hours,
        license=_license(place),
    )


@dataclass
class ExportReport:
    exported: int = 0
    skipped: Counter[str] = field(default_factory=Counter)
    by_category: Counter[str] = field(default_factory=Counter)


def export_lines(places: Iterable[Place], country: str) -> tuple[list[str], ExportReport]:
    """JSONL lines, sorted by city, category, name, id so reruns give identical files."""
    report = ExportReport()
    records: list[ContractPlace] = []
    for place in places:
        result = to_contract(place, country)
        if isinstance(result, str):
            report.skipped[result] += 1
            continue
        records.append(result)
    records.sort(key=lambda r: (r.city.casefold(), r.category, r.name.casefold(), r.id))
    for record in records:
        report.by_category[record.category] += 1
    report.exported = len(records)
    lines = [json.dumps(r.model_dump(mode="json"), ensure_ascii=False) for r in records]
    return lines, report


def render_report(report: ExportReport, out: Path) -> str:
    lines = [f"Exported {report.exported} places to {out}"]
    for category, count in sorted(report.by_category.items()):
        lines.append(f"  {category:<10} {count:>5}")
    for reason, count in report.skipped.most_common():
        lines.append(f"  skipped {count}: {reason}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.places.export", description=__doc__)
    parser.add_argument("--city", required=True)
    parser.add_argument("--country", required=True, help='English name, e.g. "Japan".')
    parser.add_argument("--out", type=Path, default=None, help="Default data/export/<city>.jsonl")
    return parser


def main(argv: Sequence[str] | None = None, engine: Engine | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = engine or make_engine()
    try:
        create_tables(engine)
        with session_scope(engine) as session:
            places = repo.search_places(session, city=args.city)
    except OperationalError as exc:
        print(f"Could not use the database: {exc.orig}", file=sys.stderr)
        return 2
    if not places:
        print(f"No places for {args.city!r}. Run `ingest` and `enrich` first.", file=sys.stderr)
        return 1

    lines, report = export_lines(places, args.country)
    # Same file names as the scrapers: "San Diego" -> san-diego, "São Paulo" -> s-o-paulo.
    slug = re.sub(r"[^a-z0-9]+", "-", args.city.lower()).strip("-") or "city"
    out = args.out or Path("data/export") / f"{slug}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    print(render_report(report, out))
    return 0 if lines else 1


if __name__ == "__main__":
    sys.exit(main())
