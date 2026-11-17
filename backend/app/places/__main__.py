"""Clean scraped data, remove duplicates, and look at what is in the database.

uv run python -m app.places ingest data/raw/sedona.json --dry-run   # no database
uv run python -m app.places ingest data/raw/sedona.json             # save to the database
uv run python -m app.places show Sedona --category eat --limit 5
uv run python -m app.places stats
uv run python -m app.places init-db --reset                         # erase all places
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from app.places import repo
from app.places.db import create_tables, make_engine, reset_tables, session_scope
from app.places.dedupe import MergeNote
from app.places.ingest import IngestReport, ingest
from app.places.models import Category, Place
from app.scraping.models import ScrapeResult


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.places", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="Clean, de-duplicate and save a scraped JSON file.")
    p.add_argument("file", type=Path, help="JSON written by `python -m app.scraping`.")
    p.add_argument("--dry-run", action="store_true", help="Don't touch the database.")
    p.add_argument("--examples", type=int, default=8, help="How many merged duplicates to show.")

    p = sub.add_parser("show", help="List places from the database.")
    p.add_argument("city", nargs="?")
    p.add_argument("--category", choices=[c.value for c in Category])
    p.add_argument("--search", help="Part of a name.")
    p.add_argument("--limit", type=int, default=10)

    sub.add_parser("stats", help="Count places per city and type.")

    p = sub.add_parser("init-db", help="Create the tables (safe to repeat).")
    p.add_argument("--reset", action="store_true", help="Erase every place first.")
    return parser


def main(argv: Sequence[str] | None = None, engine: Engine | None = None) -> int:
    args = build_parser().parse_args(argv)
    needs_db = not (args.command == "ingest" and args.dry_run)
    engine = engine or (make_engine() if needs_db else None)
    try:
        if args.command == "ingest":
            return _ingest(args, engine)
        assert engine is not None
        if args.command == "show":
            return _show(args, engine)
        if args.command == "stats":
            return _stats(engine)
        return _init_db(args, engine)
    except OperationalError as exc:
        print(f"Could not use the database: {exc.orig}", file=sys.stderr)
        print("Check DATABASE_URL in backend/.env (see backend/.env.example).", file=sys.stderr)
        return 2


# ---- commands ----------------------------------------------------------------


def _ingest(args: argparse.Namespace, engine: Engine | None) -> int:
    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    scrape = ScrapeResult.model_validate_json(args.file.read_text(encoding="utf-8"))
    print(f"Read {len(scrape.listings)} listings from {args.file}")

    if engine is None:
        report = ingest(scrape.listings, None)
        print(render_ingest(report, examples=args.examples))
        print("\nDry run: nothing was saved.")
        return 0

    create_tables(engine)
    with session_scope(engine) as session:
        report = ingest(scrape.listings, session)
    print(render_ingest(report, examples=args.examples))
    print(f"\nSaved to {engine.url.render_as_string(hide_password=True)}")
    return 0


def render_ingest(report: IngestReport, *, examples: int = 8) -> str:
    lines = [f"Kept {report.cleaned} of {report.raw} after cleaning."]
    for reason, count in report.dropped.most_common():
        lines.append(f"  dropped {count}: {reason}")
    lines.append(
        f"Duplicates removed: {report.duplicates_removed}"
        + (f"   (same listing seen again: {report.refreshed})" if report.refreshed else "")
    )
    shown = [m for m in report.merges if not m.is_refresh][:examples]
    for note in shown:
        lines.append(f"  - {_describe_merge(note)}")
    hidden = len([m for m in report.merges if not m.is_refresh]) - len(shown)
    if hidden > 0:
        lines.append(f"  ... and {hidden} more")
    if report.saved:
        lines.append(
            f"Database: {report.inserted} new, {report.updated} updated, {report.deleted} removed."
        )
    for city, count in report.per_city.items():
        lines.append(f"{city}: {count} places")
    return "\n".join(lines)


def _describe_merge(note: MergeNote) -> str:
    extra = []
    if note.name_score is not None:
        extra.append(f"names {note.name_score:.0f}/100")
    if note.distance_m is not None:
        extra.append(f"{note.distance_m:.0f} m apart")
    detail = f" [{', '.join(extra)}]" if extra else ""
    folded = " + ".join(f'"{name}"' for name in note.merged)
    return f'"{note.kept}" absorbed {folded}: {note.reason}{detail}'


def _show(args: argparse.Namespace, engine: Engine) -> int:
    with session_scope(engine) as session:
        places = repo.search_places(
            session,
            city=args.city,
            category=Category(args.category) if args.category else None,
            text=args.search,
            limit=args.limit,
        )
    if not places:
        print("No places found. Run `ingest` first.")
        return 1
    for place in places:
        print(format_place(place))
    return 0


def format_place(place: Place) -> str:
    where = f"{place.city} / {place.district}" if place.district else place.city
    lines = [f"[{place.category.value}] {place.name}  ({where})"]
    detail = (
        ("address", place.address),
        ("near", place.directions),
        ("lat/lng", f"{place.lat}, {place.lng}" if place.has_coordinates else None),
        ("hours", place.opening_hours),
        ("price", place.price_text),
        ("about", (place.description or "")[:110] or None),
        ("source", f"{place.source_url}  (fetched {place.fetched_at:%Y-%m-%d})"),
    )
    lines += [f"    {label:<8} {value}" for label, value in detail if value]
    if len(place.sources) > 1:
        lines.append(f"    also in  {len(place.sources) - 1} other source page(s)")
    return "\n".join(lines)


def _stats(engine: Engine) -> int:
    with session_scope(engine) as session:
        rows = repo.count_by_city_and_category(session)
        if not rows:
            print("The database is empty. Run `ingest` first.")
            return 1
        print(f"{'city':<20} {'see':>5} {'do':>5} {'eat':>5} {'sleep':>5} {'total':>6}")
        cities = sorted({city for city, _, _ in rows})
        for city in cities:
            counts = {cat: n for c, cat, n in rows if c == city}
            total = sum(counts.values())
            print(
                f"{city:<20} {counts.get('see', 0):>5} {counts.get('do', 0):>5} "
                f"{counts.get('eat', 0):>5} {counts.get('sleep', 0):>5} {total:>6}"
            )
            places = repo.search_places(session, city=city)
            for label, have in (
                ("coordinates", sum(p.has_coordinates for p in places)),
                ("address", sum(p.address is not None for p in places)),
                ("opening hours", sum(p.opening_hours is not None for p in places)),
                ("price", sum(p.price_text is not None for p in places)),
            ):
                print(f"    with {label:<14} {have:>5} / {total}  ({100 * have // total}%)")
    return 0


def _init_db(args: argparse.Namespace, engine: Engine) -> int:
    if args.reset:
        reset_tables(engine)
        print("Erased and re-created the places table.")
    else:
        create_tables(engine)
        print("Tables are ready.")
    print(f"Database: {engine.url.render_as_string(hide_password=True)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
