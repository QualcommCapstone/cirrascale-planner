"""Run the scraper from the command line and see what it found.

    uv run python -m app.scraping "San Diego"
    uv run python -m app.scraping Tokyo --max-districts 3
    uv run python -m app.scraping Tokyo --no-districts --out data/raw/tokyo.json

It prints a summary (how many places of each type, how many have coordinates,
hours, prices...) plus a few sample places, and saves everything to a JSON file.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from app.scraping.fetch import DEFAULT_USER_AGENT, PoliteFetcher
from app.scraping.models import RawListing, ScrapeResult
from app.scraping.wikivoyage import scrape_city

COVERAGE_FIELDS = ("lat", "address", "hours", "price", "description", "website")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.scraping", description="Scrape places for a city from Wikivoyage."
    )
    parser.add_argument("city", help='Wikivoyage article name, e.g. "Tokyo" or "San Diego".')
    parser.add_argument(
        "--max-districts",
        type=int,
        default=5,
        help="How many district pages to follow for big cities (default 5).",
    )
    parser.add_argument("--no-districts", action="store_true", help="Only scrape the main page.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Where to save the JSON (default data/raw/<city>.json).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=float(os.environ.get("SCRAPER_MIN_DELAY_S", "3")),
        help="Minimum seconds between requests to the same site (default 3).",
    )
    parser.add_argument("--samples", type=int, default=3, help="Sample places to print.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show every request.")
    return parser


def main(argv: Sequence[str] | None = None, fetcher: PoliteFetcher | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # Scrapling sets up its own request logger when first imported. Import it now,
    # then only show its per-request lines with --verbose (and only once).
    from scrapling.fetchers import Fetcher  # noqa: F401

    scrapling_log = logging.getLogger("scrapling")
    scrapling_log.setLevel(logging.INFO if args.verbose else logging.WARNING)
    scrapling_log.propagate = False

    if fetcher is None:
        fetcher = PoliteFetcher(
            user_agent=os.environ.get("SCRAPER_USER_AGENT", DEFAULT_USER_AGENT),
            min_delay_s=args.delay,
        )

    print(
        f"Scraping Wikivoyage for {args.city!r} "
        f"(at least {fetcher.min_delay_s:g}s between requests)..."
    )
    result = scrape_city(
        args.city,
        fetcher,
        include_districts=not args.no_districts,
        max_districts=args.max_districts,
    )

    out = args.out or Path("data/raw") / f"{_slug(args.city)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")

    print(render_summary(result, samples=args.samples))
    print(f"\nSaved {len(result.listings)} places to {out}")
    return 0 if result.listings else 1


def render_summary(result: ScrapeResult, *, samples: int = 3) -> str:
    lines: list[str] = []
    listings = result.listings
    lines.append(f"\nPages fetched: {len(result.pages_fetched)}")
    for url in result.pages_fetched:
        lines.append(f"  - {url}")
    lines.append(f"Places found: {len(listings)}")
    if result.skipped:
        lines.append(f"Left out: {sum(result.skipped.values())}")
        for reason, count in sorted(result.skipped.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {count:>4}  {reason}")

    if listings:
        by_section = Counter(item.section for item in listings)
        lines.append("\nBy type:")
        for section in ("see", "do", "buy", "eat", "drink", "sleep"):
            lines.append(f"  {section:<6} {by_section.get(section, 0):>4}")

        lines.append("\nHow many places have each field:")
        for field in COVERAGE_FIELDS:
            have = sum(getattr(item, field) is not None for item in listings)
            lines.append(
                f"  {field:<12} {have:>4} / {len(listings)}  ({100 * have // len(listings)}%)"
            )

        lines.append("\nSample places:")
        for item in _pick_samples(listings, samples):
            lines.append(_format_listing(item))

    if result.errors:
        lines.append(f"\nProblems ({len(result.errors)}):")
        for error in result.errors:
            lines.append(f"  ! {error}")
    return "\n".join(lines)


def _pick_samples(listings: list[RawListing], n: int) -> list[RawListing]:
    """One sample per type first, so the preview shows variety."""
    picked: list[RawListing] = []
    seen: set[str] = set()
    for item in listings:
        if item.section not in seen:
            picked.append(item)
            seen.add(item.section)
    return picked[:n]


def _format_listing(item: RawListing) -> str:
    where = f"{item.city}" + (f" / {item.district}" if item.district else "")
    parts = [f"  [{item.section}] {item.name}  ({where})"]
    for label, value in (
        ("address", item.address),
        ("lat/lng", f"{item.lat}, {item.lng}" if item.lat is not None else None),
        ("hours", item.hours),
        ("price", item.price),
        ("source", item.source_url),
    ):
        if value:
            parts.append(f"      {label:<8} {value}")
    return "\n".join(parts)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "city"


if __name__ == "__main__":
    sys.exit(main())
