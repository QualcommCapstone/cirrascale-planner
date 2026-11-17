"""Find and merge duplicate places (the same place listed twice, or by two sources).

Two places are "the same" only if the evidence is strong. Wrongly merging two
real places (say two branches of one chain) loses a place, which is worse than
keeping a duplicate. The rules, in order:

1. Same `id` -> same (this is the same listing scraped again).
2. Same Wikidata ID -> same.
3. Different kinds of place (an eat vs a sleep) -> never the same.
   `see` and `do` count as one kind, since sources often file a place in either.
4. Both have coordinates: same if within 250 m AND the names are alike (80+/100, or
   90+ when either name is under 10 characters, since one letter then matters a lot:
   "Cafe A" vs "Cafe B"). Far apart means different places, even with an identical name.
5. A coordinate is missing: names must be near-identical (95+/100) AND something
   else must agree: the address, the phone number, or a place-specific web page
   (a chain's bare homepage doesn't count). Names alone are not enough.
   (Step 3 fills in missing coordinates, which unlocks rule 4.)

Names are compared with RapidFuzz after lowercasing, removing accents on Latin
letters, and dropping punctuation. Japanese kana are left alone on purpose
(otherwise ぱ and は would look the same).

Merging keeps the best value of each field: sources are ranked by `SOURCE_PRIORITY`,
then the newest fetch wins. The merged place keeps the id of its first member, and
the database's existing rows are passed first, so ids never change on later runs.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from app.places.models import Category, Place, SourceRef

# Higher wins when two sources disagree. Unlisted sources rank 0.
SOURCE_PRIORITY: dict[str, int] = {"wikivoyage": 10}

REASON_SAME_ID = "same listing seen again"
REASON_WIKIDATA = "same Wikidata ID"
REASON_NEAR = "same name and nearly the same spot"
REASON_CORROBORATED = "same name and matching address/phone/website"


@dataclass(frozen=True)
class Rules:
    close_m: float = 250.0
    name_score_when_close: float = 80.0
    short_name_chars: int = 10
    name_score_short_names: float = 90.0
    name_score_without_coordinates: float = 95.0
    address_score: float = 85.0


@dataclass
class MergeNote:
    """One merge, for the report: who was kept, who was folded in, and why."""

    kept: str
    merged: list[str]
    reason: str
    name_score: float | None = None
    distance_m: float | None = None

    @property
    def is_refresh(self) -> bool:
        return self.reason == REASON_SAME_ID


@dataclass
class DedupeResult:
    places: list[Place]
    merges: list[MergeNote] = field(default_factory=list)

    @property
    def duplicates_removed(self) -> int:
        return sum(len(m.merged) for m in self.merges if not m.is_refresh)

    @property
    def refreshed(self) -> int:
        return sum(len(m.merged) for m in self.merges if m.is_refresh)


@dataclass(frozen=True)
class Match:
    reason: str
    name_score: float | None = None
    distance_m: float | None = None


# ---- comparing two places ------------------------------------------------------


def normalize_name(name: str) -> str:
    """Lowercase, drop accents on Latin letters, drop punctuation and a leading 'the'."""
    decomposed = unicodedata.normalize("NFKD", name.casefold())
    kept: list[str] = []
    for ch in decomposed:
        if unicodedata.combining(ch) and kept and ord(kept[-1]) < 0x250:
            continue  # accent on a Latin letter
        kept.append(ch)
    text = unicodedata.normalize("NFC", "".join(kept))
    text = re.sub(r"[^\w]+", " ", text).strip()
    return re.sub(r"^the ", "", text)


def distance_m(a: Place, b: Place) -> float | None:
    """Straight-line distance in metres (good enough at city scale)."""
    if a.lat is None or a.lng is None or b.lat is None or b.lng is None:
        return None
    mean_lat = math.radians((a.lat + b.lat) / 2)
    dy = (b.lat - a.lat) * 111_320
    dx = (b.lng - a.lng) * 111_320 * math.cos(mean_lat)
    return math.hypot(dx, dy)


def _kind(category: Category) -> str:
    return "see_do" if category in (Category.SEE, Category.DO) else category.value


def _digits(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def _site_key(url: str | None) -> str | None:
    """A web page specific to one place. A bare homepage is shared by a whole chain, so
    it says nothing about which branch this is, and gives None.
    """
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    return f"{host}{path}" if host and path else None


def find_match(
    a: Place, b: Place, rules: Rules, names: tuple[str, str] | None = None
) -> Match | None:
    """Decide whether two places are the same. Returns why, or None."""
    if a.id == b.id:
        return Match(REASON_SAME_ID)
    if _kind(a.category) != _kind(b.category):
        return None
    if a.wikidata_id and a.wikidata_id == b.wikidata_id:
        return Match(REASON_WIKIDATA)

    name_a, name_b = names or (normalize_name(a.name), normalize_name(b.name))
    if not name_a or not name_b:
        return None

    dist = distance_m(a, b)
    if dist is not None:
        if dist > rules.close_m:
            return None
        score = fuzz.token_sort_ratio(name_a, name_b)
        short = min(len(name_a), len(name_b)) < rules.short_name_chars
        needed = rules.name_score_short_names if short else rules.name_score_when_close
        if score >= needed:
            return Match(REASON_NEAR, name_score=score, distance_m=dist)
        return None

    score = fuzz.token_sort_ratio(name_a, name_b)
    if score < rules.name_score_without_coordinates:
        return None
    if _corroborated(a, b, rules):
        return Match(REASON_CORROBORATED, name_score=score)
    return None


def _corroborated(a: Place, b: Place, rules: Rules) -> bool:
    if a.address and b.address:
        addr_a, addr_b = normalize_name(a.address), normalize_name(b.address)
        if fuzz.token_sort_ratio(addr_a, addr_b) >= rules.address_score:
            return True
    phone_a, phone_b = _digits(a.phone), _digits(b.phone)
    if len(phone_a) >= 6 and phone_a == phone_b:
        return True
    site_a, site_b = _site_key(a.website), _site_key(b.website)
    return site_a is not None and site_a == site_b


# ---- merging ---------------------------------------------------------------------


def source_rank(place: Place) -> tuple[int, float]:
    """Sort key: best source first, then newest fetch."""
    return (-SOURCE_PRIORITY.get(place.source, 0), -place.fetched_at.timestamp())


def merge_group(members: list[Place]) -> Place:
    """Combine places known to be the same into one. `members[0]` supplies the id."""
    if len(members) == 1:
        return members[0]

    ranked = sorted(members, key=source_rank)
    best = ranked[0]

    def first(attr: str) -> Any:
        for place in ranked:
            value = getattr(place, attr)
            if value not in (None, "", []):
                return value
        return None

    # Coordinates travel as a pair, taken from the best source that has both.
    coords = next(((p.lat, p.lng) for p in ranked if p.has_coordinates), (None, None))

    sources: dict[tuple[str, str], SourceRef] = {}
    for place in members:
        for ref in place.sources:
            key = (ref.source, ref.url)
            if key not in sources or ref.fetched_at > sources[key].fetched_at:
                sources[key] = ref

    tags = sorted({tag for place in members for tag in place.tags})

    return Place(
        id=members[0].id,
        name=best.name,
        city=best.city,
        district=first("district"),
        address=first("address"),
        directions=first("directions"),
        lat=coords[0],
        lng=coords[1],
        category=best.category,
        source_section=best.source_section,
        subsection=best.subsection,
        description=first("description"),
        opening_hours=first("opening_hours"),
        opening_hours_osm=first("opening_hours_osm"),
        price_text=first("price_text"),
        price_range=first("price_range"),
        price_estimate=first("price_estimate"),
        price_currency=first("price_currency"),
        tags=tags,
        indoor=first("indoor"),
        website=first("website"),
        phone=first("phone"),
        wikidata_id=first("wikidata_id"),
        source=best.source,
        source_url=best.source_url,
        fetched_at=best.fetched_at,
        sources=sorted(sources.values(), key=lambda r: (r.source, r.url)),
    )


# ---- the whole list ---------------------------------------------------------------


def dedupe(places: list[Place], rules: Rules | None = None) -> DedupeResult:
    """Remove duplicates. Order is kept: each group sits where its first member was."""
    rules = rules or Rules()
    n = len(places)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    reasons: dict[int, list[Match]] = {}
    names = [normalize_name(p.name) for p in places]

    # Same id first, whatever the kind: a page often repeats a place as a short stub
    # (listed in full under See, then again under Do), and a re-scrape repeats it too.
    first_with_id: dict[object, int] = {}
    for i, place in enumerate(places):
        if place.id not in first_with_id:
            first_with_id[place.id] = i
        else:
            keep = first_with_id[place.id]
            parent[i] = keep
            reasons.setdefault(keep, []).append(Match(REASON_SAME_ID))
    # Only places of the same city and kind can match, so compare within those blocks.
    blocks: dict[tuple[str, str], list[int]] = {}
    for i, place in enumerate(places):
        blocks.setdefault((place.city.casefold(), _kind(place.category)), []).append(i)

    for indices in blocks.values():
        for pos, i in enumerate(indices):
            for j in indices[pos + 1 :]:
                match = find_match(places[i], places[j], rules, (names[i], names[j]))
                if match is None:
                    continue
                root_i, root_j = find(i), find(j)
                if root_i == root_j:
                    continue
                keep, drop = min(root_i, root_j), max(root_i, root_j)
                parent[drop] = keep
                reasons.setdefault(keep, []).append(match)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    merged: list[Place] = []
    notes: list[MergeNote] = []
    for root in sorted(groups):
        members = [places[i] for i in groups[root]]
        merged.append(merge_group(members))
        if len(members) > 1:
            first_match = reasons[root][0]
            notes.append(
                MergeNote(
                    kept=members[0].name,
                    merged=[m.name for m in members[1:]],
                    reason=first_match.reason,
                    name_score=first_match.name_score,
                    distance_m=first_match.distance_m,
                )
            )
    return DedupeResult(places=merged, merges=notes)
