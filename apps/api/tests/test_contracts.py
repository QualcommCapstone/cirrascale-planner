import json
import pathlib

from app.schemas.trip import SimplePlanRequest, Trip, TripRequest

SAMPLE = pathlib.Path(__file__).resolve().parents[3] / "packages/contracts/examples/sample-trip.json"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text())


def test_pydantic_trip_validates_the_canonical_sample():
    trip = Trip.model_validate(load_sample())
    assert trip.title
    assert trip.stops[0].city == "Kyoto"
    act = trip.stops[0].days[0].activities[0]
    assert act.verified is True
    assert act.sourceUrl and act.sourceUrl.startswith("https://")


def test_trip_round_trips_without_losing_fields():
    data = load_sample()
    dumped = Trip.model_validate(data).model_dump(mode="json")
    # Field names are byte-compatible with the frontend (camelCase preserved).
    assert dumped["stops"][0]["dayStart"] == 1
    assert dumped["stops"][0]["days"][0]["activities"][0]["durationMins"] == 120


def test_trip_request_accepts_goal_and_preferences():
    req = TripRequest.model_validate({"goal": "6 days in Japan", "preferences": load_sample()["preferences"]})
    assert req.goal == "6 days in Japan"
    assert req.preferences.budget == "Mid"


def test_trip_request_rejects_empty_and_overlong_goal():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TripRequest.model_validate({"goal": ""})
    with pytest.raises(ValidationError):
        TripRequest.model_validate({"goal": "x" * 401})


def test_simple_adapter_contract_parses():
    req = SimplePlanRequest.model_validate(
        {"destination": "Tokyo", "days": 4, "budget": 1500, "currency": "USD",
         "preferences": ["technology", "vegetarian food", "anime"]}
    )
    assert req.destination == "Tokyo"
    assert req.days == 4
