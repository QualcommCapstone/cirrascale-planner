"""Interest tags and the indoor/outdoor flag, worked out from a place's own text.

These are simple, readable keyword rules, not a model, so the same place always gets
the same answer and you can see exactly why (tests list every rule). When the evidence
is thin or mixed we say nothing (`indoor=None`, fewer tags) instead of guessing.

Evidence used, strongest first:
- The "headline": the name, the Wikivoyage heading ("Museums") and the listing type
  (`source_section`: buy, drink ...). Always used.
- The opening of the description (first 200 characters), only for `see` and `do` places that
  aren't shops, and for indoor/outdoor only when the headline says nothing. Long
  descriptions mention everything nearby ("next to the park, a museum..."), and a quiet cafe
  near a park is not an outdoors place.
"""

from __future__ import annotations

import re

from app.places.models import Category, Place


def _words(csv: str) -> list[str]:
    return [w.strip() for w in csv.split(",") if w.strip()]


# tag -> words that signal it. Matched on whole words, plural allowed.
TAG_RULES: dict[str, list[str]] = {
    "food": _words(
        "restaurant, cafe, coffee, bakery, diner, eatery, izakaya, ramen, sushi, noodle, "
        "pizzeria, bistro, brasserie, steakhouse, grill, street food, food court, "
        "food hall, market hall, tapas, dim sum, curry, tempura, yakitori, tonkatsu, "
        "okonomiyaki, burger, taco"
    ),
    "nightlife": _words(
        "bar, pub, club, nightclub, lounge, cocktail, karaoke, brewery, taproom, izakaya, "
        "speakeasy, disco, nightlife, beer garden, gay bar"
    ),
    "shopping": _words(
        "shop, store, mall, market, boutique, souvenir, department store, shopping, "
        "arcade, outlet, bookstore, bookshop, flea market"
    ),
    "museum": _words("museum, gallery, exhibition, exhibit, planetarium, science center"),
    "art": _words("art, gallery, sculpture, mural, artist, painting, ukiyo-e"),
    "history": _words(
        "historic, history, castle, ruins, ruin, monument, memorial, fort, fortress, "
        "palace, ancient, heritage, battlefield, archaeological, old town, samurai, "
        "shogun, war"
    ),
    "culture": _words(
        "temple, shrine, theater, theatre, kabuki, noh, festival, traditional, cultural, "
        "cathedral, church, mosque, synagogue, opera, tea ceremony, geisha, library"
    ),
    "religious": _words(
        "temple, shrine, church, cathedral, mosque, synagogue, monastery, mission, pilgrimage"
    ),
    "outdoors": _words(
        "park, garden, trail, hike, hiking, beach, lake, mountain, canyon, river, forest, "
        "waterfall, viewpoint, overlook, vista, campground, trailhead, cliff, scenic, "
        "island, coast, butte, peak, ridge, falls, mesa"
    ),
    "nature": _words(
        "park, garden, forest, canyon, wildlife, waterfall, lake, nature, botanical, zoo, "
        "aquarium, reserve, national park, river, beach"
    ),
    "hiking": _words("trail, hike, hiking, trailhead, trek, summit, climb"),
    "beach": _words("beach, shore, seaside, coast"),
    "views": _words(
        "viewpoint, overlook, vista, observation deck, observatory, panoramic, skyline, "
        "scenic view, lookout, sky tree, skytree"
    ),
    "family": _words(
        "kids, children, child, family, zoo, aquarium, theme park, playground, amusement, "
        "kid-friendly, toy"
    ),
    "entertainment": _words(
        "theme park, arcade, cinema, karaoke, amusement, casino, concert, theater, "
        "theatre, comedy, gaming, game center"
    ),
    "music": _words("music, live music, jazz, concert, orchestra, opera, live house, band"),
    "sports": _words(
        "stadium, sumo, baseball, soccer, football, golf, ski, skiing, climbing, tennis, "
        "arena, gym, swimming, surf, surfing, kayak, fitness, race course, racecourse"
    ),
    "wellness": _words(
        "spa, onsen, hot spring, sento, massage, yoga, bathhouse, sauna, wellness, retreat"
    ),
    "architecture": _words("architecture, architect, skyscraper, landmark"),
    "hotel": _words("hotel, inn, resort, motel, lodge"),
    "camping": _words("campground, campsite, camping, camp, rv park, glamping"),
    "hostel": _words("hostel, capsule, backpackers, dorm"),
    "ryokan": _words("ryokan, minshuku, guesthouse, guest house, bed and breakfast, b&b"),
}

# Tags every place of a type gets, whatever its words say.
SECTION_TAGS: dict[str, list[str]] = {
    "eat": ["food"],
    "drink": ["nightlife"],
    "buy": ["shopping"],
}
# Words that make a "drink" place more of a cafe than a bar.
_CAFE_WORDS = re.compile(r"\b(cafes?|coffee|tea|bakery|patisserie|dessert)\b")

# Evidence that a place is indoors or outdoors. Both present means mixed, so we say None.
INDOOR_WORDS = _words(
    "museum, gallery, aquarium, theater, theatre, cinema, mall, department store, arcade, "
    "library, karaoke, planetarium, spa, hotel, hostel, ryokan, bathhouse, sento, casino, "
    "opera, concert hall, shopping, store, bookstore, izakaya, restaurant, cafe, bar, pub, "
    "club, nightclub, bakery, cathedral, church"
)
OUTDOOR_WORDS = _words(
    "park, garden, gardens, beach, trail, hike, hiking, trailhead, mountain, canyon, lake, "
    "river, viewpoint, overlook, vista, forest, waterfall, campground, camp, island, "
    "coast, bridge, plaza, square, street, market, festival, beer garden, rooftop, "
    "terrace, yatai, food truck, ruins, cliff, zoo, trek, summit, butte, peak, ridge, falls, mesa"
)

# Eating and sleeping places are indoors unless the name says otherwise.
_DEFAULT_INDOOR = (Category.EAT, Category.SLEEP)
_OPEN_AIR_WORDS = _words(
    "food truck, yatai, campground, campsite, camping, camp, rv park, glamping, street food, "
    "beer garden"
)
_PARTLY_OUTDOOR_WORDS = _words("rooftop, terrace, patio, garden, outdoor seating, open-air")
# Nightlife words strong enough to count even for a place listed under "Eat".
_NIGHTLIFE_STRONG = _words(
    "club, nightclub, pub, cocktail, karaoke, brewery, taproom, speakeasy, lounge, nightlife"
)

_MAX_TAGS = 8


def _compile(words: list[str]) -> re.Pattern[str]:
    parts = sorted({re.escape(w) for w in words}, key=len, reverse=True)
    return re.compile(r"(?<![\w-])(?:" + "|".join(parts) + r")(?:e?s)?(?![\w-])")


_TAG_PATTERNS = {tag: _compile(words) for tag, words in TAG_RULES.items()}
_OPEN_AIR = _compile(_OPEN_AIR_WORDS)
_PARTLY_OUTDOOR = _compile(_PARTLY_OUTDOOR_WORDS)
_NIGHTLIFE_STRONG_RE = _compile(_NIGHTLIFE_STRONG)
_INDOOR = _compile(INDOOR_WORDS)
_OUTDOOR = _compile(OUTDOOR_WORDS)


_BODY_CHARS = 200


# Natural places named after buildings: "Cathedral Rock", "Church Peak", "Temple Mountain".
# Keep the natural word and drop the building word, so they aren't read as churches.
_NATURAL_FEATURE = re.compile(
    r"\b(?:cathedral|church|temple|chapel|mission|castle|fort|palace)\s+"
    r"(rock|peak|mountain|mount|butte|canyon|hill|ridge|spire|creek|falls|point)\b"
)


def headline_text(place: Place) -> str:
    text = f"{place.name} {place.subsection or ''}".lower()
    return _NATURAL_FEATURE.sub(r"\1", text)


def body_text(place: Place) -> str:
    """The start of the description, for places where it describes the place itself."""
    if place.category not in (Category.SEE, Category.DO) or place.source_section == "buy":
        return ""
    return (place.description or "")[:_BODY_CHARS].lower()


def _tags_in(text: str) -> set[str]:
    return {tag for tag, pattern in _TAG_PATTERNS.items() if pattern.search(text)}


def interest_tags(place: Place) -> list[str]:
    """Interest tags for a place, sorted, at most 8."""
    text = headline_text(place)
    tags = _tags_in(text)
    if len(tags) < 2:  # the name says little, so let the description add more
        tags |= _tags_in(body_text(place))
    tags.update(SECTION_TAGS.get(place.source_section, []))

    if place.source_section == "eat":
        tags.add("food")
        if not _NIGHTLIFE_STRONG_RE.search(text) and place.source_section == "eat":
            tags.discard("nightlife")  # "Sushi Bar" is dinner, not nightlife
    if place.category is Category.SLEEP:
        tags -= {"food", "nightlife", "shopping", "outdoors", "nature", "views", "history"}
        if not tags & {"hostel", "ryokan", "camping"}:
            tags.add("hotel")
    if place.source_section == "drink" and _CAFE_WORDS.search(text):
        tags.discard("nightlife")
        tags.add("food")
    if place.source_section == "buy":
        tags -= {"food", "architecture", "history", "outdoors", "nature"}  # "Tower Records"
    if "museum" in tags:
        tags.discard("shopping")
    return sorted(tags)[:_MAX_TAGS]


def _side(text: str) -> bool | None:
    """True = indoor words only, False = outdoor words only, None = neither or both."""
    indoor, outdoor = bool(_INDOOR.search(text)), bool(_OUTDOOR.search(text))
    if indoor == outdoor:
        return None
    return indoor


def indoor_flag(place: Place) -> bool | None:
    """True = indoors, False = outdoors, None = unknown or a mix."""
    headline = headline_text(place)
    if place.category in _DEFAULT_INDOOR:
        if _OPEN_AIR.search(headline):
            return False
        if _PARTLY_OUTDOOR.search(headline):
            return None
        return True
    answer = _side(headline)
    if answer is None and not (_INDOOR.search(headline) and _OUTDOOR.search(headline)):
        answer = _side(body_text(place))  # the name was silent, so read the description's start
    return answer
