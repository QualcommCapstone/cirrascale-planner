"""Proposed dedupe change (D7 in docs/data-ingestion-spec.md). Needs Aayush's review.

`find_match` compares the kind of place before the Wikidata ID, so two records with
the same Wikidata ID never merge when the sources filed them differently. OSM files a
market as `amenity=marketplace` (buy -> do); Wikivoyage may list the same market under
Eat. A shared Wikidata ID is the strongest identity signal we have.

Proposal: check the Wikidata ID before the kind. This test fails today on purpose
(strict xfail): when the change is made, it starts passing and pytest flags it, so the
marker gets removed in the same commit.
"""

from __future__ import annotations

import pytest

from app.places.dedupe import Rules, dedupe, find_match
from app.places.models import Category
from tests.factories import place


def _market_pair() -> tuple[object, object]:
    osm = place(
        "Tsukiji Outer Market",
        source="osm",
        source_url="https://www.openstreetmap.org/way/1",
        category=Category.DO,
        source_section="buy",
        wikidata_id="Q1189046",
        lat=35.6654,
        lng=139.7707,
    )
    wikivoyage = place(
        "Tsukiji Outer Market",
        category=Category.EAT,
        source_section="eat",
        wikidata_id="Q1189046",
    )
    return osm, wikivoyage


@pytest.mark.xfail(strict=True, reason="D7: find_match checks kind before Wikidata ID")
def test_same_wikidata_id_matches_across_kinds() -> None:
    osm, wikivoyage = _market_pair()
    assert find_match(osm, wikivoyage, Rules()) is not None  # type: ignore[arg-type]


@pytest.mark.xfail(strict=True, reason="D7: dedupe blocks by kind before comparing")
def test_dedupe_merges_same_wikidata_id_across_kinds() -> None:
    osm, wikivoyage = _market_pair()
    assert len(dedupe([osm, wikivoyage]).places) == 1  # type: ignore[list-item]
