import json

from fastapi.testclient import TestClient

from app.fixtures import load_fixture_places
from app.main import app
from app.schemas.trip import DEFAULT_PREFERENCES
from app.services import normalize

JAPAN = {"goal": "6 days in Japan", "preferences": {"interests": ["Food"], "budget": "Mid", "pace": "Balanced"}}


def ndjson(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_plan_streams_outline_stops_done():
    with TestClient(app) as client:  # context manager runs lifespan -> seeds store
        r = client.post("/api/v1/plan", json=JAPAN)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/x-ndjson")
        events = ndjson(r.text)
        types = [e["type"] for e in events]

        assert types[0] == "outline"
        assert types[-1] == "done"
        assert "stop" in types

        outline = events[0]["trip"]
        assert outline["stops"] and outline["preferences"]["budget"] == "Mid"

        done = events[-1]
        assert done["ms"] >= 0
        assert done["estimatedCostUsd"] is not None  # totals computed

        first_stop = next(e for e in events if e["type"] == "stop")
        act = first_stop["days"][0]["activities"][0]
        for key in ["id", "slot", "name", "verified", "category", "cost", "sourceUrl"]:
            assert key in act


def test_chat_returns_updated_trip():
    with TestClient(app) as client:
        outline = ndjson(client.post("/api/v1/plan", json=JAPAN).text)[0]["trip"]
        r = client.post("/api/v1/chat", json={"trip": outline, "message": "add more food stops"})
        assert r.status_code == 200
        body = r.json()
        assert body["stops"] and body["title"]


def test_normalize_grounds_activities_in_retrieved_places():
    # An activity whose name matches a retrieved place is verified with its source.
    places = load_fixture_places()
    fushimi = next(p for p in places if "Fushimi" in p.name)
    days_json = {
        "days": [
            {
                "day": 1,
                "morning": {"name": fushimi.name, "neighborhood": "Fushimi", "durationMins": 120,
                            "cost": "free", "category": "culture", "reason": "Torii gates.", "sourceId": fushimi.id},
                "afternoon": {"name": "Unknown Invented Place", "neighborhood": "", "durationMins": 60,
                              "cost": "$", "category": "sight", "reason": "x"},
            }
        ]
    }
    days = normalize.build_days(days_json, 1, 1, places)
    acts = {a.slot: a for a in days[0].activities}
    assert acts["morning"].verified is True
    assert acts["morning"].sourceUrl == fushimi.source_url
    assert acts["morning"].lat == fushimi.lat  # coords taken from the verified place
    assert acts["afternoon"].verified is False  # invented place is flagged, not trusted


def test_build_trip_shell_rejects_junk():
    assert normalize.build_trip_shell({"nope": 1}, "goal", DEFAULT_PREFERENCES) is None
    assert normalize.build_trip_shell(None, "goal", DEFAULT_PREFERENCES) is None
