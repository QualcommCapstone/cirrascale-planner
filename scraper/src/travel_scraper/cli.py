"""Command-line tool.

    uv run python -m travel_scraper osm Tokyo --country Japan
    uv run python -m travel_scraper fill-coords ../backend/data/raw/tokyo.json
    uv run python -m travel_scraper discover Tokyo --country Japan --categories museums
    uv run python -m travel_scraper crawl Tokyo --country Japan --max-pages 40
    uv run python -m travel_scraper collect Tokyo --country Japan --discover

Raw files go to backend/data/raw/ (Aayush's `ingest` reads them from there).
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from travel_scraper.config import Settings, get_settings
from travel_scraper.handoff import (
    SECTIONS,
    ListingSection,
    ScrapeResult,
    median_center,
    raw_path,
    read_result,
    slug,
    write_result,
)
from travel_scraper.http import ApiClient
from travel_scraper.osm.query import QUERY_TIMEOUT_S


def _center(text: str) -> tuple[float, float]:
    try:
        lat_s, lng_s = text.split(",")
        lat, lng = float(lat_s), float(lng_s)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use lat,lng e.g. 35.68,139.76") from exc
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise argparse.ArgumentTypeError("lat/lng out of range")
    return lat, lng


def _sections(text: str) -> tuple[ListingSection, ...]:
    chosen = tuple(s.strip() for s in text.split(",") if s.strip())
    bad = [s for s in chosen if s not in SECTIONS]
    if bad:
        raise argparse.ArgumentTypeError(f"unknown sections {bad}; choose from {SECTIONS}")
    return chosen  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m travel_scraper",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    def city_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("city", help='e.g. "Tokyo" (same name as the Wikivoyage article)')
        p.add_argument("--country", required=True, help='English name, e.g. "Japan".')

    p = sub.add_parser("osm", help="Collect places from OpenStreetMap (Overpass API).")
    city_args(p)
    p.add_argument("--center", type=_center, help="lat,lng (default: from the Wikivoyage raw file)")
    p.add_argument("--radius-km", type=float, default=15.0)
    p.add_argument("--max-per-section", type=int, default=300)
    p.add_argument("--sections", type=_sections, default=SECTIONS)
    p.add_argument("--out", type=Path)

    p = sub.add_parser("fill-coords", help="Fill missing coordinates from Wikidata, in place.")
    p.add_argument("file", type=Path)

    p = sub.add_parser("discover", help="Find candidate pages with DuckDuckGo.")
    city_args(p)
    p.add_argument("--categories", default="attractions,museums,restaurants,activities")
    p.add_argument("--max-results", type=int, default=10, help="Per query.")
    p.add_argument("--out", type=Path)

    p = sub.add_parser("crawl", help="Crawl eligible discovered pages with Scrapy.")
    city_args(p)
    p.add_argument("--discovered", type=Path, help="Default data/discovery/<city>.jsonl")
    p.add_argument("--max-urls", type=int, default=20, help="Eligible URLs to start from.")
    p.add_argument("--max-pages", type=int, default=50)
    p.add_argument("--max-depth", type=int, default=1)
    p.add_argument("--playwright", action="store_true", help="Render JS-only pages (needs extra).")
    p.add_argument("--center", type=_center, help="Drop places far from this lat,lng.")
    p.add_argument("--out", type=Path)

    p = sub.add_parser("collect", help="The whole pipeline for one city.")
    city_args(p)
    p.add_argument("--max-districts", type=int, default=10)
    p.add_argument("--discover", action="store_true", help="Also run discovery + crawl.")
    p.add_argument("--playwright", action="store_true")
    p.add_argument("--max-per-section", type=int, default=300)
    p.add_argument("--max-pages", type=int, default=50)
    p.add_argument("--skip-wikivoyage", action="store_true", help="Reuse the existing raw file.")
    p.add_argument("--dry-run", action="store_true", help="Raw files + dry-run ingest only.")
    p.add_argument(
        "--database-url", help="Override backend DATABASE_URL, e.g. sqlite:///data/planner.db"
    )
    p.add_argument(
        "--ingest-api",
        action="store_true",
        help="Check the JSONL with apps/api ingest (mock mode; nothing reaches Qdrant).",
    )
    return parser


def api_client(settings: Settings) -> ApiClient:
    from urllib.parse import urlsplit

    return ApiClient(
        user_agent=settings.user_agent,
        min_delay_s={
            urlsplit(settings.overpass_url).netloc: settings.overpass_delay_s,
            urlsplit(settings.wikidata_url).netloc: settings.wikidata_delay_s,
            "*": 1.0,
        },
        # Longer than the Overpass query timeout, so we never give up on a query the
        # server is still running (and then hit 429 for holding two slots).
        timeout_s=QUERY_TIMEOUT_S + 60,
        # Public APIs that are busy need minutes, not seconds: 10 s, 20 s, 40 s.
        backoff_s=10.0,
    )


def resolve_center(
    city: str, given: tuple[float, float] | None, settings: Settings
) -> tuple[float, float]:
    if given is not None:
        return given
    path = raw_path(settings.raw_dir, city)
    if path.exists():
        center = median_center(read_result(path))
        if center is not None:
            return center
    raise SystemExit(
        f"No city center for {city!r}: pass --center lat,lng, or scrape Wikivoyage first "
        f"(expected {path})."
    )


def summarize(result: ScrapeResult, path: Path) -> str:
    listings = result.listings
    lines = [f"{result.source}: {len(listings)} places for {result.city} -> {path}"]
    by_section: dict[str, int] = {}
    for item in listings:
        by_section[item.section] = by_section.get(item.section, 0) + 1
    if by_section:
        lines.append("  " + ", ".join(f"{k} {v}" for k, v in sorted(by_section.items())))
    with_coords = sum(x.lat is not None for x in listings)
    if listings:
        lines.append(f"  with coordinates: {with_coords}/{len(listings)}")
    for reason, count in sorted(result.skipped.items(), key=lambda kv: -kv[1]):
        lines.append(f"  skipped {count}: {reason}")
    for error in result.errors:
        lines.append(f"  ! {error}")
    return "\n".join(lines)


# ---- commands ----------------------------------------------------------------


def cmd_osm(args: argparse.Namespace, settings: Settings) -> int:
    from travel_scraper.osm.scrape import scrape_osm

    center = resolve_center(args.city, args.center, settings)
    with api_client(settings) as client:
        result = scrape_osm(
            args.city,
            center,
            client,
            overpass_url=settings.overpass_url,
            radius_km=args.radius_km,
            max_per_section=args.max_per_section,
            sections=args.sections,
        )
    path = write_result(result, args.out or raw_path(settings.raw_dir, args.city, "osm"))
    print(summarize(result, path))
    # A failed section is reported above; the others are still good data.
    return 0 if result.listings else 1


def cmd_fill(args: argparse.Namespace, settings: Settings) -> int:
    from travel_scraper.wikidata import fill_coordinates

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 2
    result = read_result(args.file)
    with api_client(settings) as client:
        report = fill_coordinates(result, client, url=settings.wikidata_url)
    write_result(result, args.file)
    print(
        f"Wikidata: {report.filled} of {report.candidates} listings without coordinates filled "
        f"({report.not_found} had none on Wikidata, {report.failed_batches} failed batches)"
    )
    return 0 if report.failed_batches == 0 else 1


def discovery_path(settings: Settings, city: str) -> Path:
    return settings.data_dir / "discovery" / f"{slug(city)}.jsonl"


def cmd_discover(args: argparse.Namespace, settings: Settings) -> int:
    from travel_scraper.discovery.discover import discover
    from travel_scraper.discovery.duckduckgo import DuckDuckGoProvider

    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    provider = DuckDuckGoProvider(delay_s=settings.search_delay_s)
    try:
        result = discover(
            args.city, args.country, categories, provider, max_results=args.max_results
        )
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    path = result.write(args.out or discovery_path(settings, args.city))
    rejected: dict[str, int] = {}
    for url in result.urls:
        if not url.eligible:
            rejected[url.reason] = rejected.get(url.reason, 0) + 1
    print(f"Discovered {len(result.urls)} URLs, {len(result.eligible)} eligible -> {path}")
    for reason, count in sorted(rejected.items(), key=lambda kv: -kv[1]):
        print(f"  rejected {count}: {reason}")
    for failure in result.failed_queries:
        print(f"  ! search failed: {failure}")
    return 0 if result.urls else 1


def cmd_crawl(args: argparse.Namespace, settings: Settings) -> int:
    from travel_scraper.crawl.run import crawl
    from travel_scraper.discovery.discover import read_discovered

    source = args.discovered or discovery_path(settings, args.city)
    if not source.exists():
        print(f"No discovery file {source}. Run `discover` first.", file=sys.stderr)
        return 2
    eligible = sorted(
        (u for u in read_discovered(source) if u.eligible), key=lambda u: (u.priority, u.url)
    )
    urls = [u.url for u in eligible][: args.max_urls]
    center = args.center
    if center is None:
        path = raw_path(settings.raw_dir, args.city)
        center = median_center(read_result(path)) if path.exists() else None
    if args.playwright:
        try:
            import scrapy_playwright  # noqa: F401
        except ImportError:
            print(
                "--playwright needs: uv sync --extra playwright && uv run playwright install "
                "chromium",
                file=sys.stderr,
            )
            return 2
    result = crawl(
        urls,
        args.city,
        user_agent=settings.user_agent,
        delay_s=settings.crawl_delay_s,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        playwright=args.playwright,
        center=center,
    )
    path = write_result(result, args.out or raw_path(settings.raw_dir, args.city, "web"))
    print(f"Crawled {len(urls)} start URLs")
    print(summarize(result, path))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    settings = get_settings()
    if args.command == "osm":
        return cmd_osm(args, settings)
    if args.command == "fill-coords":
        return cmd_fill(args, settings)
    if args.command == "discover":
        return cmd_discover(args, settings)
    if args.command == "crawl":
        return cmd_crawl(args, settings)
    from travel_scraper.collect import cmd_collect

    return cmd_collect(args, settings)


if __name__ == "__main__":
    sys.exit(main())
