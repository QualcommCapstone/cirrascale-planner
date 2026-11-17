"""Cleaning raw listings into the shared Place format."""

from __future__ import annotations

import pytest

from app.places.clean import (
    DROP_NO_NAME,
    DROP_NO_SOURCE,
    clean_coordinates,
    clean_listing,
    clean_listings,
    clean_value,
    split_address,
)
from app.places.models import Category, Place, make_place_id
from tests.factories import WHEN, raw


@pytest.mark.parametrize(
    ("section", "category"),
    [
        ("see", "see"),
        ("do", "do"),
        ("buy", "do"),
        ("eat", "eat"),
        ("drink", "eat"),
        ("sleep", "sleep"),
    ],
)
def test_wikivoyage_types_map_to_four_categories(section, category):
    place = clean_listing(raw(section=section))
    assert isinstance(place, Place)
    assert place.category == Category(category)
    assert place.source_section == section  # original type kept for the tags step


def test_keeps_source_link_and_date():
    place = clean_listing(raw("Fire Museum"))
    assert isinstance(place, Place)
    assert place.source_url == "https://en.wikivoyage.org/wiki/Testville#Fire_Museum"
    assert place.fetched_at == WHEN
    assert [(s.source, s.url) for s in place.sources] == [("wikivoyage", place.source_url)]


def test_id_is_stable_for_the_same_listing():
    first = clean_listing(raw("Fire Museum"))
    again = clean_listing(raw("Fire Museum", description="changed text", hours="9-5"))
    assert isinstance(first, Place) and isinstance(again, Place)
    assert first.id == again.id == make_place_id("wikivoyage", first.source_url)


def test_text_is_tidied():
    place = clean_listing(
        raw(
            "  Fire   Museum ",
            description="Big [1] hall \n with  trucks.[edit]",
            district=" Shinjuku ",
        )
    )
    assert isinstance(place, Place)
    assert place.name == "Fire Museum"
    assert place.description == "Big hall with trucks."
    assert place.district == "Shinjuku"


def test_fullwidth_and_halfwidth_characters_are_normalized():
    place = clean_listing(raw("ＡＢＣ Cafe", phone="ﾃｽﾄ"))
    assert isinstance(place, Place)
    assert place.name == "ABC Cafe"
    assert place.phone == "テスト"


@pytest.mark.parametrize("junk", ["", "  ", "?", "n/a", "N/A.", "TBD", "unknown", "-"])
def test_placeholder_values_become_empty(junk):
    place = clean_listing(raw(hours=junk, price=junk, phone=junk))
    assert isinstance(place, Place)
    assert place.opening_hours is None and place.price_text is None and place.phone is None


def test_hours_and_price_text_are_kept_as_written():
    place = clean_listing(raw(hours="09:30-17:00, closed on Mondays", price="¥1200"))
    assert isinstance(place, Place)
    assert place.opening_hours == "09:30-17:00, closed on Mondays"
    assert place.price_text == "¥1200"
    assert place.price_range is None and place.tags == [] and place.indoor is None


@pytest.mark.parametrize(
    "hint",
    [
        "located in front of Ueno station",
        "Near the park",
        "next to the bank",
        "5 minutes from the pier",
        "Just past the bridge",
    ],
)
def test_directions_are_not_addresses(hint):
    assert split_address(hint, None) == (None, hint)


def test_real_addresses_stay_addresses():
    assert split_address("780 Chapel Rd", "by the creek") == ("780 Chapel Rd", "by the creek")
    assert split_address("Yotsuya 4-10", None) == ("Yotsuya 4-10", None)


def test_existing_directions_are_not_overwritten_by_address_hint():
    assert split_address("near the station", "2 min walk") == (None, "2 min walk")


@pytest.mark.parametrize(
    ("lat", "lng", "expected"),
    [
        (35.6, 139.7, (35.6, 139.7)),
        (0.0, 0.0, (None, None)),
        (35.6, None, (None, None)),
        (None, 139.7, (None, None)),
    ],
)
def test_coordinates(lat, lng, expected):
    assert clean_coordinates(lat, lng) == expected


@pytest.mark.parametrize("name", ["", "   ", "---", "!!!"])
def test_nameless_listings_are_dropped_with_a_reason(name):
    # RawListing needs min_length=1, so build it with a placeholder and patch the name.
    listing = raw("x").model_copy(update={"name": name})
    assert clean_listing(listing) == DROP_NO_NAME


def test_listing_without_a_source_link_is_dropped():
    assert clean_listing(raw("Park").model_copy(update={"source_url": ""})) == DROP_NO_SOURCE
    assert (
        clean_listing(raw("Park").model_copy(update={"source_url": "not a link"})) == DROP_NO_SOURCE
    )


def test_clean_listings_counts_what_it_drops():
    listings = [raw("Good"), raw("x").model_copy(update={"name": "--"}), raw("Also Good")]
    places, report = clean_listings(listings)
    assert [p.name for p in places] == ["Good", "Also Good"]
    assert report.dropped == {DROP_NO_NAME: 1}
    assert report.total_dropped == 1


def test_bad_website_is_ignored_not_fatal():
    place = clean_listing(raw(website="javascript:alert(1)"))
    assert isinstance(place, Place) and place.website is None


def test_clean_value_helper():
    assert clean_value(" 10:00 - 18:00 ") == "10:00 - 18:00"
    assert clean_value(None) is None


def test_embedding_text_is_plain_and_complete():
    place = clean_listing(
        raw(
            "Pasutakan",
            section="eat",
            subsection="Budget",
            district="Shinjuku",
            description="Okonomiyaki cooked at your table.",
            price="¥1200",
        )
    )
    assert isinstance(place, Place)
    assert place.embedding_text() == (
        "Pasutakan (eat) in Shinjuku, Testville. Budget. "
        "Okonomiyaki cooked at your table. Price: ¥1200."
    )
