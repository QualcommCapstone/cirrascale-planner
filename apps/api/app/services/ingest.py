"""Standalone ingestion: JSONL place records -> validate -> embed -> upsert.

Kept separate from the user-facing planning endpoint (no scraping in /plan).
Idempotent: a place id always maps to the same vector-store id, so re-ingesting
updates rather than duplicates. Batches embedding calls.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

from pydantic import BaseModel, ValidationError

from app.providers import Providers, UpsertItem
from app.schemas.place import Place


class IngestError(BaseModel):
    line: int
    place_id: str | None
    reason: str


class IngestReport(BaseModel):
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    errors: list[IngestError] = []


async def _embed_and_upsert(places: list[Place], providers: Providers) -> int:
    if not places:
        return 0
    vectors = await providers.embedding.embed_documents([p.embedding_text() for p in places])
    return await providers.vector_store.upsert_places(
        [UpsertItem(p, v) for p, v in zip(places, vectors, strict=True)]
    )


async def ingest_records(
    records: Iterable[str], providers: Providers, batch_size: int = 64
) -> IngestReport:
    """`records` yields raw JSONL lines. Invalid lines are reported, not fatal."""
    report = IngestReport()
    batch: list[Place] = []

    async def flush() -> None:
        report.succeeded += await _embed_and_upsert(batch, providers)
        batch.clear()

    for i, line in enumerate(records, start=1):
        line = line.strip()
        if not line:
            continue
        report.total += 1
        try:
            place = Place.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as err:
            report.failed += 1
            pid = None
            try:
                pid = json.loads(line).get("id")
            except Exception:
                pass
            report.errors.append(IngestError(line=i, place_id=pid, reason=str(err)[:200]))
            continue
        batch.append(place)
        if len(batch) >= batch_size:
            await flush()

    await flush()
    return report
