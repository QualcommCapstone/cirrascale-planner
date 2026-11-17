from app.config import Settings
from app.fixtures import load_fixture_places
from app.providers import build_providers
from app.services.ingest import ingest_records


async def test_ingest_reports_valid_and_invalid_lines():
    providers = build_providers(Settings())  # mock / memory
    places = load_fixture_places()
    lines = [p.model_dump_json() for p in places]
    lines.append("{ not json")           # malformed
    lines.append('{"id": "x"}')          # missing required fields

    report = await ingest_records(iter(lines), providers)

    assert report.total == len(lines)
    assert report.succeeded == len(places)
    assert report.failed == 2
    assert {e.line for e in report.errors} == {len(places) + 1, len(places) + 2}


async def test_ingest_is_idempotent():
    providers = build_providers(Settings())
    lines = [p.model_dump_json() for p in load_fixture_places()]

    await ingest_records(iter(lines), providers)
    await ingest_records(iter(lines), providers)  # re-ingest the same records

    # Keyed by place id -> no duplicates after a second pass.
    store = providers.vector_store
    assert len(store._items) == len(lines)  # type: ignore[attr-defined]
