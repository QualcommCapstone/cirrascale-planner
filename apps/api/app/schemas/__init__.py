"""Canonical API schemas. The models in `trip` mirror the frontend Zod contract."""

from app.schemas.trip import (
    Activity,
    ChatRequest,
    Day,
    DoneEvent,
    ErrorEvent,
    FoodPick,
    Leg,
    OutlineEvent,
    Photo,
    Preferences,
    SimplePlanRequest,
    Stay,
    Stop,
    StopErrorEvent,
    StopEvent,
    Trip,
    TripRequest,
)

# Every model that should appear in the generated OpenAPI/TypeScript contract.
CONTRACT_MODELS = [
    TripRequest,
    Preferences,
    Photo,
    Activity,
    Day,
    FoodPick,
    Stay,
    Stop,
    Leg,
    Trip,
    OutlineEvent,
    StopEvent,
    StopErrorEvent,
    DoneEvent,
    ErrorEvent,
    SimplePlanRequest,
    ChatRequest,
]

__all__ = [m.__name__ for m in CONTRACT_MODELS]
