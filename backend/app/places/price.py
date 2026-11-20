"""Turn price text into a price level and a rough cost.

    "¥1,200"                  -> estimate 1200 JPY
    "¥2,000-3,000"            -> estimate 2500 JPY (middle of the range)
    "Free; donations welcome" -> free

The level (`free` / `low` / `mid` / `high`, the same values as `cost.level` in
docs/itinerary-schema.md) is chosen in this order:

1. The text says it's free.
2. Wikivoyage's own heading ("Budget", "Mid-range", "Splurge"). Editors judge these against
   local prices, so they beat any conversion we could do.
3. The amount, converted to US dollars with a rough fixed rate and compared with typical
   prices for that kind of place. Good enough to sort places, not to quote a price.
4. Otherwise unknown (None). We never make up a level.

`estimate` is the FIRST amount in the text (e.g. the adult ticket, or a single room), so
treat it as a rough per-person figure for the budget tracker, not an exact quote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.places.models import Category, PriceRange

# Rough US-dollar value of one unit. Only used to sort places into low/mid/high.
USD_RATE: dict[str, float] = {"USD": 1.0, "JPY": 0.0067, "EUR": 1.08, "GBP": 1.27}

_SYMBOLS = {"¥": "JPY", "円": "JPY", "$": "USD", "€": "EUR", "£": "GBP"}
_CODES = {
    "jpy": "JPY",
    "yen": "JPY",
    "usd": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
}

_NUM = r"\d[\d,]*(?:\.\d+)?"
_BEFORE = re.compile(rf"(?P<cur>[¥$€£])\s?(?P<a>{_NUM})(?:\s?[-–]\s?[¥$€£]?(?P<b>{_NUM}))?")
_AFTER = re.compile(
    rf"(?P<a>{_NUM})\s?(?P<cur>[¥円$€£]|yen\b|euros?\b|jpy\b|usd\b|eur\b|gbp\b)", re.IGNORECASE
)
_FREE = re.compile(r"^\s*(?:free|no charge|gratis)\b", re.IGNORECASE)
_BRACKETS = re.compile(r"\([^)]*\)")
_MAX_TEXT = 200  # longer text is usually a paragraph of exceptions; the first number misleads

_HEADING_LEVEL: dict[str, PriceRange] = {
    "budget": "low",
    "mid-range": "mid",
    "midrange": "mid",
    "splurge": "high",
}

# (low upper bound, mid upper bound) in USD. Above the second is "high".
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "eat": (12.0, 35.0),  # per person for a meal or drinks
    "sleep": (90.0, 220.0),  # per night
    "see": (15.0, 50.0),  # per ticket
    "do": (15.0, 50.0),
}


@dataclass(frozen=True)
class Price:
    level: PriceRange | None
    estimate: float | None = None
    currency: str | None = None


def parse_price(text: str | None, *, category: Category, subsection: str | None = None) -> Price:
    amount = _first_amount(text) if text and len(text) <= _MAX_TEXT else None
    heading = _HEADING_LEVEL.get((subsection or "").strip().lower())

    if text and _FREE.match(text):
        outside = _first_amount(_BRACKETS.sub(" ", text))  # "Free (rising to ¥1000 in 2026)"
        if outside is None or outside[0] == 0:
            return Price("free", 0.0, None)
    if amount is not None and amount[0] == 0:
        return Price("free", 0.0, amount[1])

    estimate, currency = amount if amount else (None, None)
    if category in (Category.EAT, Category.SLEEP) and heading is not None:
        return Price(heading, estimate, currency)
    if estimate is not None and currency in USD_RATE:
        return Price(_level_from_usd(estimate * USD_RATE[currency], category), estimate, currency)
    return Price(None, estimate, currency)


def _level_from_usd(usd: float, category: Category) -> PriceRange:
    low, mid = _THRESHOLDS[category.value]
    return "low" if usd < low else "mid" if usd < mid else "high"


def _first_amount(text: str) -> tuple[float, str] | None:
    """The first money amount in the text as (value, currency code), or None."""
    candidates: list[tuple[int, float, str]] = []
    for m in _BEFORE.finditer(text):
        low = _number(m.group("a"))
        high = _number(m.group("b")) if m.group("b") else None
        value = (low + high) / 2 if high is not None and high >= low else low
        candidates.append((m.start(), value, _SYMBOLS[m.group("cur")]))
    for m in _AFTER.finditer(text):
        cur = m.group("cur")
        code = _SYMBOLS.get(cur) or _CODES.get(cur.lower())
        if code:
            candidates.append((m.start(), _number(m.group("a")), code))
    if not candidates:
        return None
    _, value, code = min(candidates)
    return value, code


def _number(text: str) -> float:
    return float(text.replace(",", ""))
