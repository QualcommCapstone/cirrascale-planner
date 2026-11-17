"""Canonical trip contract — a 1:1 Pydantic mirror of the frontend's Zod model
(apps/web/src/lib/trip/types.ts).

Field names are kept in the frontend's camelCase (creditUrl, durationMins,
dayStart, stopId, ...) so JSON is byte-compatible with the existing UI and the
NDJSON streaming protocol. Do not rename without updating the Zod schema and the
generated TypeScript types in packages/contracts.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Enums (mirror the `as const` arrays in types.ts) ----------------------

Interest = Literal["Food", "Nature", "Culture", "Nightlife"]
Budget = Literal["Budget", "Mid", "Luxury"]
Pace = Literal["Relaxed", "Balanced", "Packed"]
Slot = Literal["morning", "afternoon", "evening"]
Category = Literal["sight", "food", "nature", "culture", "nightlife", "shopping"]
Cost = Literal["free", "$", "$$", "$$$"]
Mode = Literal["train", "flight", "bus", "car", "ferry"]


# --- Personalization -------------------------------------------------------


class Preferences(BaseModel):
    interests: list[Interest] = Field(default_factory=list)
    budget: Budget = "Mid"
    pace: Pace = "Balanced"


DEFAULT_PREFERENCES = Preferences()


class TripRequest(BaseModel):
    """Body of POST /api/v1/plan (and the existing /api/itinerary)."""

    goal: str = Field(min_length=1, max_length=400)
    preferences: Preferences = Field(default_factory=Preferences)


# --- Trip ------------------------------------------------------------------


class Photo(BaseModel):
    url: str
    creditUrl: str
    kind: Literal["place", "area", "city"]


class Activity(BaseModel):
    id: str
    slot: Slot
    name: str
    neighborhood: str
    durationMins: int
    cost: Cost
    category: Category
    reason: str
    lat: float | None = None
    lng: float | None = None
    verified: bool = False
    photo: Photo | None = None
    sourceUrl: str | None = None


class Day(BaseModel):
    day: int
    activities: list[Activity] = Field(default_factory=list)


class FoodPick(BaseModel):
    name: str
    note: str


class Stay(BaseModel):
    area: str
    why: str


class Stop(BaseModel):
    id: str
    city: str
    country: str
    lat: float
    lng: float
    dayStart: int
    dayEnd: int
    headline: str
    intro: str
    stay: Stay
    food: list[FoodPick] = Field(default_factory=list)
    photo: Photo | None = None
    days: list[Day] = Field(default_factory=list)


class Leg(BaseModel):
    fromId: str
    toId: str
    mode: Mode
    durationMins: int
    notes: str
    estimated: bool = False


class Trip(BaseModel):
    title: str
    summary: str
    where: str
    when: str
    days: int
    vibes: list[str] = Field(default_factory=list)
    preferences: Preferences
    stops: list[Stop] = Field(default_factory=list)
    legs: list[Leg] = Field(default_factory=list)


# --- Streaming events (NDJSON) --------------------------------------------
# One JSON object per line from POST /api/v1/plan, mirroring TripEvent.


class OutlineEvent(BaseModel):
    type: Literal["outline"] = "outline"
    trip: Trip


class StopEvent(BaseModel):
    type: Literal["stop"] = "stop"
    stopId: str
    days: list[Day]
    food: list[FoodPick]


class StopErrorEvent(BaseModel):
    type: Literal["stopError"] = "stopError"
    stopId: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    ms: int


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


TripEvent = OutlineEvent | StopEvent | StopErrorEvent | DoneEvent | ErrorEvent


# --- Optional simpler adapter contract -------------------------------------
# Not the primary contract. Accepts {destination, days, budget, currency,
# preferences:[...]} and is adapted into a TripRequest (see app/services).


class SimplePlanRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    destination: str
    days: int = Field(ge=1, le=30)
    budget: float | None = None
    currency: str = "USD"
    preferences: list[str] = Field(default_factory=list)


# --- Chat-based modification ----------------------------------------------


class ChatRequest(BaseModel):
    """Body of POST /api/v1/chat: an existing trip plus an instruction."""

    trip: Trip
    message: str = Field(min_length=1, max_length=400)
    preferences: Preferences | None = None

