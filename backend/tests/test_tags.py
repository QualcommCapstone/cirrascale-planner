"""Interest tags and indoor/outdoor. Each wrong answer found in real data has a test here."""

from __future__ import annotations

import pytest

import app.places.tags as tags_module
from app.places.models import Category as C
from app.places.tags import indoor_flag, interest_tags
from tests.factories import place


def p(name, category=C.SEE, section=None, **kw):
    return place(name, category=category, source_section=section or category.value, **kw)


# ---- tags ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(name="Setagaya Art Museum"), {"art", "museum"}),
        (dict(name="Zenpukuji Park"), {"nature", "outdoors"}),
        (dict(name="Dembō-in Temple"), {"culture", "religious"}),
        (dict(name="Meiji Jingu Stadium"), {"sports"}),
        (dict(name="Oedo Onsen Monogatari", description="A hot spring theme bath."), {"wellness"}),
        (dict(name="Cathedral Rock Trail", description="A short hike."), {"hiking", "outdoors"}),
        (dict(name="Pasta House", category=C.EAT), {"food"}),
        (dict(name="Odeon Club", category=C.EAT, section="drink"), {"nightlife"}),
        (
            dict(name="Blue Bottle Coffee", category=C.EAT, section="drink", subsection="Cafes"),
            {"food"},
        ),
        (dict(name="Melon Books", category=C.DO, section="buy"), {"shopping"}),
        (dict(name="Grand Hyatt", category=C.SLEEP), {"hotel"}),
        (dict(name="K's House Hostel", category=C.SLEEP), {"hostel"}),
        (dict(name="Hoshinoya Ryokan", category=C.SLEEP), {"ryokan"}),
        (dict(name="Rancho Sedona RV Park", category=C.SLEEP), {"camping"}),
    ],
)
def test_tags(kwargs, expected):
    assert set(interest_tags(p(**kwargs))) == expected


def test_a_bar_is_not_a_restaurant():
    """Regression: bars listed under Drink were tagged 'food'."""
    assert "food" not in interest_tags(p("IBEX", C.EAT, "drink"))


def test_sushi_bar_is_dinner_not_nightlife():
    tags = interest_tags(p("Tsukiji Sushi Bar", C.EAT, "eat"))
    assert "food" in tags and "nightlife" not in tags
    assert "nightlife" in interest_tags(p("Moonlight Cocktail Bar", C.EAT, "eat", description=""))
    assert "nightlife" in interest_tags(p("Moonlight Club", C.EAT, "eat"))


def test_shops_ignore_their_description_and_non_shopping_words():
    """Regression: Don Quijote got 'entertainment' and 'family' from a long description."""
    store = p(
        "Don Quijote",
        C.DO,
        "buy",
        description="Discount store with toys, an arcade and kids' games.",
    )
    assert interest_tags(store) == ["shopping"]
    assert "architecture" not in interest_tags(p("Tower Records", C.DO, "buy", subsection="Music"))


def test_description_helps_only_when_the_name_says_little():
    vague = p("Ikefukurō", description="A lovely botanical garden with a pond.")
    assert {"nature", "outdoors"} <= set(interest_tags(vague))
    clear = p("Art Museum", description="Next to a park, a zoo and a beach.")
    assert set(interest_tags(clear)) == {"art", "museum"}


def test_only_the_start_of_a_description_counts():
    far = p("Ikefukurō", description="A neighborhood. " + "x " * 120 + "There is a park nearby.")
    assert interest_tags(far) == []


def test_eating_places_ignore_their_description():
    cafe = p(
        "Quiet Corner", C.EAT, "eat", description="A hidden place near the park and the shrine."
    )
    assert interest_tags(cafe) == ["food"]


def test_lodging_never_gets_activity_tags():
    assert interest_tags(p("Park Hyatt Garden Hotel", C.SLEEP)) == ["hotel"]


def test_museum_beats_shopping():
    assert "shopping" not in interest_tags(p("Museum Shop and Gallery", C.SEE))


def test_unknown_place_gets_no_tags_rather_than_a_guess():
    assert interest_tags(p("Ōi Horse", description="A thing.")) == []


def test_tags_are_sorted_and_capped():
    many = p("Park Garden Museum Theatre Temple Beach Trail Gallery Hotel Castle Zoo")
    result = interest_tags(many)
    assert result == sorted(result) and len(result) <= 8


def test_vocabulary_has_no_broken_terms():
    for words in (
        *tags_module.TAG_RULES.values(),
        tags_module.INDOOR_WORDS,
        tags_module.OUTDOOR_WORDS,
    ):
        assert all(w and w == w.strip() and "," not in w for w in words)
    assert (
        "food hall" in tags_module.TAG_RULES["food"] and "hall" not in tags_module.TAG_RULES["food"]
    )


# ---- indoor / outdoor ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (dict(name="Setagaya Art Museum"), True),
        (dict(name="Tokyo Aquarium"), True),
        (dict(name="Zenpukuji Park"), False),
        (dict(name="Cathedral Rock Trail"), False),
        (dict(name="Hozho Plaza", category=C.DO, section="buy"), False),
        (dict(name="Lumine Department Store", category=C.DO, section="buy"), True),
        (dict(name="Pasta House", category=C.EAT), True),
        (dict(name="Grand Hyatt", category=C.SLEEP), True),
        (dict(name="Sakura Beer Garden", category=C.EAT, section="drink"), False),
        (dict(name="Yatai Ramen Stall", category=C.EAT), False),
        (dict(name="Rancho Sedona RV Park", category=C.SLEEP), False),
        (dict(name="Sky Rooftop Bar", category=C.EAT, section="drink"), None),
        (dict(name="Ikefukurō"), None),
        (dict(name="Tokyo Budokan"), None),
    ],
)
def test_indoor_flag(kwargs, expected):
    assert indoor_flag(p(**kwargs)) is expected


def test_museum_in_a_park_is_indoor_because_the_name_wins():
    assert indoor_flag(p("Garden Museum")) is None  # name itself is mixed
    assert indoor_flag(p("National Museum of Nature and Science")) is True


def test_description_decides_only_when_the_name_is_silent():
    assert indoor_flag(p("Ikefukurō", description="A pleasant garden by the river.")) is False
    assert indoor_flag(p("Ikefukurō", description="A garden museum.")) is None


def test_mixed_evidence_is_unknown_not_a_guess():
    assert indoor_flag(p("Zoo and Aquarium")) is None


def test_shops_never_use_descriptions_for_indoor():
    # A street of shops says "stores" but is not an indoor place.
    assert (
        indoor_flag(p("Kappabashi", C.DO, "buy", description="A street of kitchen stores.")) is None
    )
