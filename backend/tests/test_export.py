"""Export to the backend's JSONL contract (`python -m app.places.export`)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from app.places import repo
from app.places.db import session_scope
from app.places.export import (
    SKIP_LODGING,
    SKIP_NO_COORDINATES,
    ContractPlace,
    contract_category,
    export_lines,
    main,
    to_contract,
)
from app.places.models import Category, SourceRef
from tests.factories import place

TOKYO = {"lat": 35.68, "lng": 139.76}


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({"category": Category.EAT, "source_section": "drink"}, "nightlife"),
        ({"category": Category.DO, "source_section": "buy"}, "shopping"),
        ({"category": Category.EAT, "source_section": "eat"}, "food"),
        ({"category": Category.SLEEP, "source_section": "sleep"}, None),
        ({"tags": ["outdoors", "history"]}, "nature"),
        ({"tags": ["views"]}, "nature"),
        ({"tags": ["museum"]}, "culture"),
        ({"tags": ["religious"]}, "culture"),
        ({"category": Category.DO, "source_section": "do", "tags": ["nightlife"]}, "nightlife"),
        ({"tags": ["shopping"]}, "shopping"),
        ({"tags": ["family"]}, "sight"),
        ({}, "sight"),
    ],
)
def test_category_mapping(kw: dict[str, object], expected: str | None) -> None:
    assert contract_category(place(**kw)) == expected


def test_full_record_matches_contract() -> None:
    p = place(
        "Tokyo National Museum",
        city="Tokyo",
        description="Japan's oldest museum.",
        address="13-9 Ueno Park",
        opening_hours="Tu-Su 9:30-17:00",
        price_range="low",
        tags=["museum"],
        **TOKYO,
    )
    record = to_contract(p, "Japan")
    assert isinstance(record, ContractPlace)
    data = record.model_dump(mode="json")
    assert data["id"] == str(p.id)
    assert data["country"] == "Japan"
    assert data["category"] == "culture"
    assert data["price_level"] == "$"
    assert data["collected_at"].startswith("2026-11-08")
    assert data["source_attribution"] == "Wikivoyage contributors"
    assert data["license"] == "CC BY-SA 4.0"
    assert set(data) == set(ContractPlace.model_fields)


def test_missing_values_follow_contract_defaults() -> None:
    record = to_contract(place(**TOKYO), "Japan")
    assert isinstance(record, ContractPlace)
    assert record.description == ""
    assert record.price_level is None


@pytest.mark.parametrize(("level", "expected"), [("free", "free"), ("mid", "$$"), ("high", "$$$")])
def test_price_levels(level: str, expected: str) -> None:
    record = to_contract(place(price_range=level, **TOKYO), "Japan")
    assert isinstance(record, ContractPlace)
    assert record.price_level == expected


def test_skips_places_without_coordinates_and_lodging() -> None:
    assert to_contract(place(), "Japan") == SKIP_NO_COORDINATES
    hotel = place(category=Category.SLEEP, source_section="sleep", **TOKYO)
    assert to_contract(hotel, "Japan") == SKIP_LODGING


def test_merged_sources_list_every_attribution_and_license() -> None:
    when = datetime(2026, 11, 8, tzinfo=UTC)
    p = place(
        sources=[
            SourceRef(
                source="wikivoyage", url="https://en.wikivoyage.org/wiki/T#a", fetched_at=when
            ),
            SourceRef(source="osm", url="https://www.openstreetmap.org/node/1", fetched_at=when),
            SourceRef(source="web", url="https://www.museum.example.jp/en/", fetched_at=when),
        ],
        **TOKYO,
    )
    record = to_contract(p, "Japan")
    assert isinstance(record, ContractPlace)
    assert record.source_attribution == (
        "Wikivoyage contributors; © OpenStreetMap contributors; museum.example.jp"
    )
    assert record.license == "CC BY-SA 4.0; ODbL 1.0; see source"


def test_lines_are_sorted_and_reported() -> None:
    places = [
        place("Zoo Park", tags=["nature"], **TOKYO),
        place("Akihabara", tags=["shopping"], **TOKYO),
        place("Hotel A", category=Category.SLEEP, source_section="sleep", **TOKYO),
        place("No Pin"),
        place("Bistro", category=Category.EAT, source_section="eat", **TOKYO),
    ]
    lines, report = export_lines(places, "Japan")
    names = [json.loads(line)["name"] for line in lines]
    assert names == ["Bistro", "Zoo Park", "Akihabara"]  # food < nature < shopping
    assert report.exported == 3
    assert report.skipped == {SKIP_LODGING: 1, SKIP_NO_COORDINATES: 1}
    assert export_lines(list(reversed(places)), "Japan")[0] == lines  # stable


def test_cli_writes_jsonl(engine: Engine, tmp_path: Path) -> None:
    with session_scope(engine) as session:
        repo.save_places(session, [place("Senso-ji", city="Tokyo", tags=["religious"], **TOKYO)])
    out = tmp_path / "tokyo.jsonl"
    assert main(["--city", "Tokyo", "--country", "Japan", "--out", str(out)], engine=engine) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["category"] == "culture"
    ContractPlace.model_validate(rows[0])


def test_cli_with_empty_city_fails(engine: Engine, tmp_path: Path) -> None:
    out = tmp_path / "x.jsonl"
    assert main(["--city", "Nowhere", "--country", "X", "--out", str(out)], engine=engine) == 1
