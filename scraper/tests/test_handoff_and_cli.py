"""Handoff format helpers and CLI argument handling."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from travel_scraper.cli import _center, _sections, build_parser, resolve_center
from travel_scraper.config import Settings
from travel_scraper.handoff import (
    RawListing,
    ScrapeResult,
    median_center,
    raw_path,
    read_result,
    write_result,
)

WHEN = datetime(2026, 11, 17, tzinfo=UTC)


def _listing(name: str, lat: float | None, lng: float | None) -> RawListing:
    return RawListing(
        source="osm",
        source_url=f"https://www.openstreetmap.org/node/{name}",
        page_url="https://www.openstreetmap.org/",
        fetched_at=WHEN,
        city="Tokyo",
        section="see",
        name=name,
        lat=lat,
        lng=lng,
    )


def test_round_trip(tmp_path: Path) -> None:
    result = ScrapeResult(
        source="osm", city="Tokyo", started_at=WHEN, listings=[_listing("1", 1.0, 2.0)]
    )
    result.skip("x")
    result.skip("x", 2)
    path = write_result(result, tmp_path / "a" / "tokyo-osm.json")
    assert read_result(path) == result
    assert result.skipped == {"x": 3}


def test_raw_path_names_match_backend() -> None:
    assert raw_path(Path("d"), "San Diego") == Path("d/san-diego.json")
    assert raw_path(Path("d"), "Tokyo", "osm") == Path("d/tokyo-osm.json")


def test_median_center() -> None:
    result = ScrapeResult(source="w", city="Tokyo", started_at=WHEN, listings=[
        _listing("a", 1.0, 10.0), _listing("b", 2.0, 20.0), _listing("c", 30.0, 300 - 200),
        _listing("d", None, None),
    ])  # fmt: skip
    assert median_center(result) == (2.0, 20.0)
    assert median_center(ScrapeResult(source="w", city="x", started_at=WHEN)) is None


def test_center_and_sections_parsing() -> None:
    assert _center("35.68,139.76") == (35.68, 139.76)
    for bad in ("35.68", "a,b", "95,10"):
        with pytest.raises(Exception, match=r"lat|range"):
            _center(bad)
    assert _sections("see,eat") == ("see", "eat")
    with pytest.raises(Exception, match="unknown sections"):
        _sections("see,spa")


def test_country_is_required() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["osm", "Tokyo"])
    args = build_parser().parse_args(["osm", "Tokyo", "--country", "Japan"])
    assert args.country == "Japan"


def test_resolve_center_needs_a_source(tmp_path: Path) -> None:
    settings = Settings(backend_dir=tmp_path)
    with pytest.raises(SystemExit, match="--center"):
        resolve_center("Tokyo", None, settings)
    assert resolve_center("Tokyo", (1.0, 2.0), settings) == (1.0, 2.0)
    result = ScrapeResult(
        source="wikivoyage", city="Tokyo", started_at=WHEN, listings=[_listing("a", 35.0, 139.0)]
    )
    write_result(result, raw_path(settings.raw_dir, "Tokyo"))
    assert resolve_center("Tokyo", None, settings) == (35.0, 139.0)
