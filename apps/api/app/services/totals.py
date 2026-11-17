"""Rough cost estimate from structured data only (no invented prices).

Uses activity cost tiers, nights by budget, and legs by mode. A ballpark for the
UI, never presented as a quote.
"""

from __future__ import annotations

from app.schemas.trip import Trip

_ACTIVITY_USD = {"free": 0.0, "$": 15.0, "$$": 40.0, "$$$": 90.0}
_NIGHT_USD = {"Budget": 45.0, "Mid": 130.0, "Luxury": 360.0}
_LEG_USD = {"train": 60.0, "flight": 160.0, "bus": 25.0, "car": 70.0, "ferry": 40.0}


def estimate_total_usd(trip: Trip) -> float:
    total = 0.0
    for stop in trip.stops:
        nights = max(0, stop.dayEnd - stop.dayStart)
        total += nights * _NIGHT_USD.get(trip.preferences.budget, 130.0)
        for day in stop.days:
            for act in day.activities:
                total += _ACTIVITY_USD.get(act.cost, 15.0)
    for leg in trip.legs:
        total += _LEG_USD.get(leg.mode, 50.0)
    return round(total, 2)
