"""Fill in the derived fields of a place: price level, structured hours, tags, indoor/outdoor.

Everything here is worked out from the place's own text (see hours.py, price.py, tags.py),
and always recomputed from scratch, so improving a rule and re-running `enrich` fixes
old rows too, with no re-scrape. It never invents data: a field stays empty when the text
doesn't support an answer.
"""

from __future__ import annotations

from app.places.hours import parse_hours
from app.places.models import Place
from app.places.price import parse_price
from app.places.tags import indoor_flag, interest_tags


def enrich(place: Place) -> Place:
    price = parse_price(place.price_text, category=place.category, subsection=place.subsection)
    return place.model_copy(
        update={
            "opening_hours_osm": parse_hours(place.opening_hours),
            "price_range": price.level,
            "price_estimate": price.estimate,
            "price_currency": price.currency,
            "tags": interest_tags(place),
            "indoor": indoor_flag(place),
        }
    )


def enrich_all(places: list[Place]) -> list[Place]:
    return [enrich(p) for p in places]
