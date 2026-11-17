"""v1 planning API: streaming plan + chat-based modification."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.schemas.trip import ChatRequest, TripRequest
from app.services.rag import generate_trip, plan_trip

router = APIRouter(prefix="/api/v1", tags=["planning"])


async def _ndjson(request_body: TripRequest, providers) -> asyncio.AsyncGenerator[bytes, None]:
    """Bridge the emit-based pipeline to a non-buffered NDJSON stream."""
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(event: dict) -> None:
        await queue.put(event)

    async def run() -> None:
        try:
            await generate_trip(request_body, providers, emit)
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(run())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield (json.dumps(event) + "\n").encode("utf-8")
    finally:
        if not task.done():
            task.cancel()


@router.post("/plan")
async def plan(body: TripRequest, request: Request) -> StreamingResponse:
    """Stream a trip as NDJSON: outline -> stop x N -> done."""
    providers = request.app.state.providers
    return StreamingResponse(
        _ndjson(body, providers),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/chat")
async def chat(body: ChatRequest, request: Request) -> JSONResponse:
    """Apply a free-text modification by re-planning around the instruction.
    Returns the full updated Trip (non-streaming)."""
    providers = request.app.state.providers
    prefs = body.preferences or body.trip.preferences
    goal = f"{body.trip.where or body.trip.title}. Adjust the trip: {body.message}"
    trip = await plan_trip(TripRequest(goal=goal, preferences=prefs), providers)
    if trip is None:
        return JSONResponse(status_code=502, content={"error": "Couldn't update the trip."})
    return JSONResponse(content=trip.model_dump(mode="json"))
