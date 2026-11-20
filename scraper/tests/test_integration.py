"""End to end, offline: scraper output -> backend ingest/enrich/export -> apps/api ingest.

Runs the real backend/ and apps/api CLIs as subprocesses in their own uv environments
(they can't be imported here). Uses fixture data only; no network. Slower than the unit
tests (each step starts a Python process), so it's marked `integration`:

    uv run pytest -m integration
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.conftest import fixture_json, fixture_text
from travel_scraper.backends import api_dir, backend_dir, mock_api_env, run_in
from travel_scraper.crawl.extract import extract_places
from travel_scraper.crawl.run import CrawlCollector
from travel_scraper.handoff import ScrapeResult, write_result
from travel_scraper.osm.parse import parse_elements

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        shutil.which("uv") is None and not __import__("os").environ.get("SCRAPER_UV"),
        reason="needs uv to run backend/ and apps/api",
    ),
]

WHEN = datetime(2026, 11, 17, tzinfo=UTC)


def _osm_file(tmp: Path) -> Path:
    listings, _ = parse_elements(
        fixture_json("overpass_see.json")["elements"],
        section="see",
        city="Tokyo",
        fetched_at=WHEN,
        max_items=100,
    )
    result = ScrapeResult(source="osm", city="Tokyo", started_at=WHEN, listings=listings)
    return write_result(result, tmp / "tokyo-osm.json")


def _web_file(tmp: Path) -> Path:
    collector = CrawlCollector(city="Tokyo")
    page = "https://museum.example.jp/en/"
    for place in extract_places(fixture_text("jsonld_page.html"), page):
        collector.add({"place": place, "url": page})
    for place in extract_places(fixture_text("microdata_page.html"), "https://sushi.example.jp/"):
        collector.add({"place": place, "url": "https://sushi.example.jp/"})
    return write_result(collector.finish({}), tmp / "tokyo-web.json")


@pytest.mark.parametrize("make", [_osm_file, _web_file], ids=["osm", "web"])
def test_backend_accepts_our_raw_files(make: object, tmp_path: Path) -> None:
    path = make(tmp_path)  # type: ignore[operator]
    run = run_in(backend_dir(), "-m", "app.places", "ingest", str(path), "--dry-run")
    assert run.returncode == 0, run.stderr
    assert "Dry run: nothing was saved." in run.stdout
    assert "failed validation" not in run.stdout


def test_full_pipeline_into_apps_api(tmp_path: Path) -> None:
    db = {"DATABASE_URL": f"sqlite:///{(tmp_path / 'planner.db').as_posix()}"}
    backend = backend_dir()
    for path in (_osm_file(tmp_path), _web_file(tmp_path)):
        run = run_in(backend, "-m", "app.places", "ingest", str(path), env=db)
        assert run.returncode == 0, run.stdout + run.stderr

    run = run_in(backend, "-m", "app.places", "enrich", "Tokyo", env=db)
    assert run.returncode == 0, run.stdout + run.stderr

    out = tmp_path / "tokyo.jsonl"
    run = run_in(
        backend,
        "-m",
        "app.places.export",
        "--city",
        "Tokyo",
        "--country",
        "Japan",
        "--out",
        str(out),
        env=db,
    )
    assert run.returncode == 0, run.stdout + run.stderr

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    names = {r["name"] for r in rows}
    assert {"Tokyo National Museum", "浅草寺", "Example Art Museum", "Sushi Example"} <= names
    assert all(r["country"] == "Japan" and r["lat"] is not None for r in rows)
    by_name = {r["name"]: r for r in rows}
    assert by_name["Tokyo National Museum"]["category"] == "culture"
    assert by_name["Sushi Example"]["category"] == "food"
    assert by_name["Tokyo National Museum"]["license"] == "ODbL 1.0"
    assert by_name["Example Art Museum"]["source_attribution"] == "museum.example.jp"
    assert by_name["浅草寺"]["price_level"] == "free"

    run = run_in(api_dir(), "-m", "app.ingest", str(out), env=mock_api_env())
    assert run.returncode == 0, run.stdout + run.stderr
    report = json.loads(run.stdout[run.stdout.index("{") :])
    assert report["failed"] == 0, report["errors"]
    assert report["succeeded"] == report["total"] == len(rows)
