"""RAG planning orchestration.

Request → validate → retrieval query → embed → vector search (filtered) →
grounded context → LLM outline → validate → per-stop: retrieve → LLM days →
validate+ground → estimate totals → stream NDJSON events.

Mirrors the frontend's outline → stop×N → done protocol. Retrieved content is
treated as data: it only ever lands in a prompt's context block, never executed.
"""

from __future__ import annotations

import asyncio
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
from app.services import monitor, normalize
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


# Candidate places handed to each day's prompt (3 slots + a little choice).
_PLACES_PER_DAY = 5


async def _retrieve(
    providers: Providers, query: str, filters: SearchFilters | None, limit: int
) -> list[Place]:
    vector = await providers.embedding.embed_query(query)
    monitor.record("embed", f"query → embedding ({len(vector)}d): “{query[:48]}”", dim=len(vector))
    results = await providers.vector_store.search(vector, filters=filters, limit=limit)
    where = []
    if filters and filters.city:
        where.append(filters.city)
    if filters and filters.categories:
        where.append("/".join(filters.categories))
    monitor.record(
        "retrieve",
        f"Qdrant → {len(results)} places" + (f" [{', '.join(where)}]" if where else ""),
        count=len(results),
        top=[r.place.name for r in results[:3]],
    )
    return [r.place for r in results]


async def _plan_day(
    providers: Providers, stop: Stop, prefs, pool: list[Place], index: int, day_num: int
):
    """Plan one day from its own slice of the retrieved pool, grounded + validated.

    A single-day object is the shape an 8B emits reliably; if parsing still fails
    build_days yields an empty day rather than killing the stop."""
    from app.schemas.trip import Day

    window = pool[index * _PLACES_PER_DAY : (index + 1) * _PLACES_PER_DAY] or pool[:_PLACES_PER_DAY]
    raw = await providers.llm.generate(
        build_days_prompt(stop.city, stop.country, day_num, day_num, prefs, window),
        max_tokens=700,
    )
    parsed = normalize.build_days(extract_json(raw), day_num, day_num, window)
    day = parsed[0] if parsed else Day(day=day_num, activities=[])
    monitor.record(
        "llm",
        f"Llama planned day {day_num} of {stop.city} → {len(day.activities)} activities",
        day=day_num,
        activities=len(day.activities),
    )
    return day


async def generate_trip(request: TripRequest, providers: Providers, emit: Emit) -> None:
    start = time.perf_counter()
    prefs = request.preferences
    monitor.record("request", f"plan requested: “{request.goal[:64]}”", interests=prefs.interests)

    # 1-5: retrieve grounding places for the whole trip, build outline.
    seed_places = await _retrieve(providers, request.goal, None, limit=12)
    outline_raw = await providers.llm.generate(
        build_outline_prompt(request.goal, prefs, seed_places), max_tokens=1200
    )
    trip = normalize.build_trip_shell(extract_json(outline_raw), request.goal, prefs)
    if trip is None:
        monitor.record("done", "outline failed to parse")
        await emit(ErrorEvent(message="Couldn't build a trip from that. Try rephrasing.").model_dump())
        return

    monitor.record("llm", f"Llama drafted outline: “{trip.title}” ({len(trip.stops)} stops)")
    await emit(OutlineEvent(trip=trip).model_dump())

    # 6-9: per stop, retrieve + plan days, grounded and validated.
    categories = [c for i in prefs.interests for c in _INTEREST_CATEGORIES.get(i, [])]
    used_ids: set[str] = set()  # places already offered, so stops don't repeat each other
    for stop in trip.stops:
        try:
            day_nums = list(range(stop.dayStart, stop.dayEnd + 1))
            filters = SearchFilters(city=stop.city, categories=categories)
            # Retrieve a generous pool, drop places earlier stops already used, then
            # give each day its own slice so neither days nor stops repeat places.
            needed = len(day_nums) * _PLACES_PER_DAY
            raw_pool = await _retrieve(
                providers,
                f"{stop.city} {stop.country} things to do",
                filters,
                max(10, needed) + len(used_ids),
            )
            fresh = [p for p in raw_pool if p.id not in used_ids]
            pool = fresh if len(fresh) >= needed else raw_pool
            used_ids.update(p.id for p in pool[:needed])
            # One LLM call per day (concurrent). An 8B reliably emits a single-day
            # object; chaining several days into one array is what it gets wrong,
            # leaving activities empty — so we never ask it to.
            days = list(
                await asyncio.gather(
                    *(_plan_day(providers, stop, prefs, pool, i, d) for i, d in enumerate(day_nums))
                )
            )
            stop.days = days
            await emit(
                StopEvent(stopId=stop.id, days=days, food=_dedupe_food(stop, days)).model_dump()
            )
        except Exception:  # one stop failing must not kill the stream
            await emit(StopErrorEvent(stopId=stop.id).model_dump())

    ms = int((time.perf_counter() - start) * 1000)
    monitor.record("done", f"itinerary complete in {ms} ms", ms=ms, stops=len(trip.stops))
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
