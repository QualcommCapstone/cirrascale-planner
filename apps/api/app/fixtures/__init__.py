"""Clearly-labeled synthetic fixtures for mock mode. NOT real recommendations."""

from __future__ import annotations

import json
import pathlib

from app.schemas.place import Place

_PLACES = pathlib.Path(__file__).with_name("places.jsonl")


def load_fixture_places() -> list[Place]:
    places: list[Place] = []
    for line in _PLACES.read_text().splitlines():
        line = line.strip()
        if line:
            places.append(Place.model_validate(json.loads(line)))
    return places
