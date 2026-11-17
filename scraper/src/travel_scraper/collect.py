"""`collect`: the whole pipeline for one city.

    Wikivoyage (backend) -> fill-coords -> OSM -> [discover -> crawl]
      -> backend ingest (each raw file) -> backend enrich -> backend export -> [apps/api ingest]

Backend steps run in backend/'s own environment (see backends.py). A source that fails
is reported and left out of ingest, so a half-collected source never replaces good data.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from travel_scraper.backends import (
    RunResult,
    api_dir,
    mock_api_env,
    run_in,
)
from travel_scraper.config import Settings
from travel_scraper.handoff import raw_path, read_result, slug


def _step(title: str) -> None:
    print(f"\n== {title}")


def _show(run: RunResult, *, tail: int = 25) -> None:
    lines = (run.stdout.strip().splitlines() or []) + (
        run.stderr.strip().splitlines() if run.returncode else []
    )
    for line in lines[-tail:]:
        print(f"   {line}")


def _db_env(args: argparse.Namespace) -> dict[str, str]:
    return {"DATABASE_URL": args.database_url} if getattr(args, "database_url", None) else {}


def cmd_collect(args: argparse.Namespace, settings: Settings) -> int:
    from travel_scraper.cli import cmd_crawl, cmd_discover, cmd_fill, cmd_osm

    backend = settings.backend_dir
    city, country = args.city, args.country
    good: list[Path] = []
    failed: list[str] = []

    # 1. Wikivoyage, through Aayush's scraper.
    wikivoyage = raw_path(settings.raw_dir, city)
    if not args.skip_wikivoyage:
        _step(f"Wikivoyage: {city}")
        run = run_in(
            backend, "-m", "app.scraping", city, "--max-districts", str(args.max_districts)
        )
        _show(run, tail=12)
        if run.returncode != 0:
            failed.append("wikivoyage")
    if wikivoyage.exists() and "wikivoyage" not in failed:
        # 2. Coordinates from Wikidata (the contract requires lat/lng).
        _step("Wikidata: fill missing coordinates")
        cmd_fill(argparse.Namespace(file=wikivoyage), settings)
        good.append(wikivoyage)

    # 3. OpenStreetMap.
    _step("OpenStreetMap (Overpass)")
    osm_args = argparse.Namespace(
        city=city,
        country=country,
        center=None,
        radius_km=15.0,
        max_per_section=args.max_per_section,
        sections=("see", "do", "buy", "eat", "drink", "sleep"),
        out=None,
    )
    try:
        osm_code = cmd_osm(osm_args, settings)
    except SystemExit as exc:  # no city center
        print(f"   {exc}")
        osm_code = 2
    osm_file = raw_path(settings.raw_dir, city, "osm")
    if osm_code == 0 and osm_file.exists():
        good.append(osm_file)
    else:
        failed.append("osm")

    # 4. Discovery + crawl (optional).
    if args.discover:
        _step("DuckDuckGo discovery")
        d_args = argparse.Namespace(
            city=city,
            country=country,
            categories="attractions,museums,restaurants,activities",
            max_results=10,
            out=None,
        )
        if cmd_discover(d_args, settings) == 0:
            _step("Crawl (Scrapy)")
            c_args = argparse.Namespace(
                city=city,
                country=country,
                discovered=None,
                max_urls=20,
                max_pages=args.max_pages,
                max_depth=1,
                playwright=args.playwright,
                center=None,
                out=None,
            )
            web_file = raw_path(settings.raw_dir, city, "web")
            if cmd_crawl(c_args, settings) == 0 and web_file.exists():
                if read_result(web_file).listings:
                    good.append(web_file)
            else:
                failed.append("web")
        else:
            failed.append("discovery")

    if not good:
        print("\nNo source produced data; nothing to ingest.")
        return 1

    # 5. Hand off to Aayush's ingest (clean -> dedupe -> database).
    env = _db_env(args)
    for path in good:
        _step(f"Ingest {path.name}" + (" (dry run)" if args.dry_run else ""))
        extra = ["--dry-run"] if args.dry_run else []
        run = run_in(backend, "-m", "app.places", "ingest", str(path.resolve()), *extra, env=env)
        _show(run, tail=12)
        if run.returncode != 0:
            print("   ingest failed; stopping.")
            return 1
    if args.dry_run:
        print("\nDry run: nothing saved.")
        return 0

    # 6. Enrich (tags, price, hours, indoor) and export to the backend contract.
    _step("Enrich")
    run = run_in(backend, "-m", "app.places", "enrich", city, env=env)
    _show(run)
    if run.returncode != 0:
        print("   enrich failed; not exporting (categories and prices would be wrong).")
        return 1
    out = (backend / "data" / "export" / f"{slug(city)}.jsonl").resolve()
    _step("Export (JSONL contract)")
    run = run_in(
        backend,
        "-m",
        "app.places.export",
        "--city",
        city,
        "--country",
        country,
        "--out",
        str(out),
        env=env,
    )
    _show(run)
    if run.returncode != 0:
        return 1

    # 7. Optional: check the file with the real backend ingestion (mock embeddings).
    if args.ingest_api:
        _step("apps/api ingest (mock embeddings, in-memory store)")
        run = run_in(api_dir(), "-m", "app.ingest", str(out), env=mock_api_env())
        report = _ingest_report(run.stdout)
        if report:
            print(
                f"   total {report.get('total')}, succeeded {report.get('succeeded')}, "
                f"failed {report.get('failed')}"
            )
            errors = report.get("errors")
            for error in (errors if isinstance(errors, list) else [])[:5]:
                print(f"   ! line {error.get('line')}: {error.get('reason')}")
        else:
            _show(run)
        if run.returncode != 0:
            return 1

    if failed:
        print(f"\nDone, but these sources failed: {', '.join(failed)}")
    print(f"\nJSONL: {out}")
    return 0


def _ingest_report(stdout: str) -> dict[str, object] | None:
    match = re.search(r"\{.*\}", stdout, re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None
