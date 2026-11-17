"""RAG planning orchestration.

Request → validate → retrieval query → embed → vector search (filtered) →
grounded context → LLM outline → validate → per-stop: retrieve → LLM days →
validate+ground → estimate totals → stream NDJSON events.

Mirrors the frontend's outline → stop×N → done protocol. Retrieved content is
treated as data: it only ever lands in a prompt's context block, never executed.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from app.providers import Providers
from app.schemas.place import Place, SearchFilters
from app.schemas.trip import (
    DoneEvent,
    ErrorEvent,
    FoodPick,
    OutlineEvent,
    Stop,
    StopErrorEvent,
    StopEvent,
    TripRequest,
)
from app.services import normalize
from app.services.parsing import extract_json
from app.services.prompts import build_days_prompt, build_outline_prompt
from app.services.totals import estimate_total_usd

Emit = Callable[[dict], Awaitable[None]]

# Category hints by interest, used to bias retrieval filters.
_INTEREST_CATEGORIES = {
    "Food": ["food"],
    "Nature": ["nature"],
    "Culture": ["culture", "sight"],
    "Nightlife": ["nightlife"],
}


async def _retrieve(
    providers: Providers, query: str, filters: SearchFilters | None, limit: int
) -> list[Place]:
    vector = await providers.embedding.embed_query(query)
    results = await providers.vector_store.search(vector, filters=filters, limit=limit)
    return [r.place for r in results]


async def generate_trip(request: TripRequest, providers: Providers, emit: Emit) -> None:
    start = time.perf_counter()
    prefs = request.preferences

    # 1-5: retrieve grounding places for the whole trip, build outline.
    seed_places = await _retrieve(providers, request.goal, None, limit=12)
    outline_raw = await providers.llm.generate(
        build_outline_prompt(request.goal, prefs, seed_places), max_tokens=1200
    )
    trip = normalize.build_trip_shell(extract_json(outline_raw), request.goal, prefs)
    if trip is None:
        await emit(ErrorEvent(message="Couldn't build a trip from that. Try rephrasing.").model_dump())
        return

    await emit(OutlineEvent(trip=trip).model_dump())

    # 6-9: per stop, retrieve + plan days, grounded and validated.
    categories = [c for i in prefs.interests for c in _INTEREST_CATEGORIES.get(i, [])]
    for stop in trip.stops:
        try:
            filters = SearchFilters(city=stop.city, categories=categories)
            stop_places = await _retrieve(providers, f"{stop.city} {stop.country} things to do", filters, 10)
            days_raw = await providers.llm.generate(
                build_days_prompt(stop.city, stop.country, stop.dayStart, stop.dayEnd, prefs, stop_places),
                max_tokens=1400,
            )
            days = normalize.build_days(extract_json(days_raw), stop.dayStart, stop.dayEnd, stop_places)
            stop.days = days
            await emit(
                StopEvent(stopId=stop.id, days=days, food=_dedupe_food(stop, days)).model_dump()
            )
        except Exception:  # one stop failing must not kill the stream
            await emit(StopErrorEvent(stopId=stop.id).model_dump())

    ms = int((time.perf_counter() - start) * 1000)
    await emit(DoneEvent(ms=ms, estimatedCostUsd=estimate_total_usd(trip)).model_dump())


def _dedupe_food(stop: Stop, days: list) -> list[FoodPick]:
    """Drop food picks that became a planned activity (parity with the web)."""
    planned = {a.name.lower() for d in days for a in d.activities}
    return [f for f in stop.food if f.name.lower() not in planned]


async def plan_trip(request: TripRequest, providers: Providers):
    """Non-streaming convenience: run the pipeline and return the assembled Trip
    (used by /api/v1/chat and tests). Returns None if generation fails."""
    from app.schemas.trip import Day, Trip

    holder: dict = {}

    async def collect(event: dict) -> None:
        if event["type"] == "outline":
            holder["trip"] = Trip.model_validate(event["trip"])
        elif event["type"] == "stop" and "trip" in holder:
            for stop in holder["trip"].stops:
                if stop.id == event["stopId"]:
                    stop.days = [Day.model_validate(d) for d in event["days"]]
                    stop.food = [FoodPick.model_validate(f) for f in event["food"]]

    await generate_trip(request, providers, collect)
    return holder.get("trip")
