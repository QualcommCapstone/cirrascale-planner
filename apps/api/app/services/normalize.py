"""Turn raw LLM JSON into validated Trip pieces, grounded in retrieved places.

Nothing reaches the response without passing through here: types are coerced,
day ranges fixed, and every activity cross-checked against the retrieved places.
An activity is `verified` only when it maps to a real retrieved place; its
sourceUrl is taken from that place (the model may not invent sources).
"""

from __future__ import annotations

from typing import Any

from app.schemas.place import Place
from app.schemas.trip import (
    SLOTS,
    Activity,
    Day,
    FoodPick,
    Leg,
    Preferences,
    Stay,
    Stop,
    Trip,
)

_VALID_COSTS = {"free", "$", "$$", "$$$"}
_VALID_CATEGORIES = {"sight", "food", "nature", "culture", "nightlife", "shopping"}
_VALID_MODES = {"train", "flight", "bus", "car", "ferry"}


def _s(v: Any, default: str = "") -> str:
    return v if isinstance(v, str) else default


def _n(v: Any, default: float) -> float:
    return float(v) if isinstance(v, (int, float)) else default


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def build_trip_shell(data: Any, request_goal: str, prefs: Preferences) -> Trip | None:
    """Parse the outline JSON into a Trip with stops (days still empty)."""
    if not isinstance(data, dict) or not isinstance(data.get("stops"), list):
        return None

    stops: list[Stop] = []
    day_cursor = 1
    for i, raw in enumerate(data["stops"]):
        if not isinstance(raw, dict):
            continue
        city = _s(raw.get("city")).strip()
        if not city:
            continue
        days = max(1, int(_n(raw.get("days"), 2)))
        stay_raw = raw.get("stay") if isinstance(raw.get("stay"), dict) else {}
        food_raw = raw.get("food") if isinstance(raw.get("food"), list) else []
        stops.append(
            Stop(
                id=f"stop-{i}-{_slug(city)}",
                city=city,
                country=_s(raw.get("country")),
                lat=_n(raw.get("lat"), 0.0),
                lng=_n(raw.get("lng"), 0.0),
                dayStart=day_cursor,
                dayEnd=day_cursor + days - 1,
                headline=_s(raw.get("headline"), city),
                intro=_s(raw.get("intro")),
                stay=Stay(area=_s(stay_raw.get("area")), why=_s(stay_raw.get("why"))),
                food=[
                    FoodPick(name=_s(f.get("name")), note=_s(f.get("note")))
                    for f in food_raw
                    if isinstance(f, dict) and _s(f.get("name"))
                ],
                photo=None,
                days=[],
            )
        )
        day_cursor += days

    if not stops:
        return None

    legs: list[Leg] = []
    raw_legs = data.get("legs") if isinstance(data.get("legs"), list) else []
    for i in range(len(stops) - 1):
        raw = raw_legs[i] if i < len(raw_legs) and isinstance(raw_legs[i], dict) else {}
        mode = _s(raw.get("mode"), "train")
        legs.append(
            Leg(
                fromId=stops[i].id,
                toId=stops[i + 1].id,
                mode=mode if mode in _VALID_MODES else "train",  # type: ignore[arg-type]
                durationMins=int(_n(raw.get("durationMins"), 120)),
                notes=_s(raw.get("notes")),
                estimated=not isinstance(raw.get("durationMins"), (int, float)),
            )
        )

    vibes = [v for v in data.get("vibes", []) if isinstance(v, str)][:4]
    return Trip(
        title=_s(data.get("title"), request_goal),
        summary=_s(data.get("summary")),
        where=_s(data.get("where")),
        when=_s(data.get("when")),
        days=stops[-1].dayEnd,
        vibes=vibes,
        preferences=prefs,
        stops=stops,
        legs=legs,
    )


def _activity(raw: Any, slot: str, by_id: dict[str, Place], by_name: dict[str, Place]) -> Activity | None:
    if not isinstance(raw, dict):
        return None
    name = _s(raw.get("name")).strip()
    if not name:
        return None

    # Ground against retrieved places: prefer the claimed sourceId, else name match.
    place = by_id.get(_s(raw.get("sourceId"))) or by_name.get(name.lower())
    verified = place is not None

    cost = _s(raw.get("cost"), "$")
    category = _s(raw.get("category"), "sight")
    lat = raw.get("lat")
    lng = raw.get("lng")
    return Activity(
        id=f"act-{slot}-{_slug(name)[:40]}",
        slot=slot,  # type: ignore[arg-type]
        name=name,
        neighborhood=_s(raw.get("neighborhood")),
        durationMins=int(_n(raw.get("durationMins"), 90)),
        cost=cost if cost in _VALID_COSTS else "$",  # type: ignore[arg-type]
        category=category if category in _VALID_CATEGORIES else "sight",  # type: ignore[arg-type]
        reason=_s(raw.get("reason")),
        lat=place.lat if place else (_n(lat, 0.0) if isinstance(lat, (int, float)) else None),
        lng=place.lng if place else (_n(lng, 0.0) if isinstance(lng, (int, float)) else None),
        verified=verified,
        photo=None,
        sourceUrl=place.source_url if place else None,
    )


def build_days(data: Any, day_start: int, day_end: int, places: list[Place]) -> list[Day]:
    """Parse the per-stop days JSON into validated Day[] grounded in `places`."""
    by_id = {p.id: p for p in places}
    by_name = {p.name.lower(): p for p in places}
    out: list[Day] = []
    raw_days = data.get("days") if isinstance(data, dict) and isinstance(data.get("days"), list) else []

    for idx, day_num in enumerate(range(day_start, day_end + 1)):
        raw = raw_days[idx] if idx < len(raw_days) and isinstance(raw_days[idx], dict) else {}
        activities: list[Activity] = []
        for slot in SLOTS:
            act = _activity(raw.get(slot), slot, by_id, by_name)
            if act:
                activities.append(act)
        out.append(Day(day=day_num, activities=activities))
    return out
