"""Ingestion CLI.

    uv run python -m app.ingest path/to/places.jsonl
    uv run python -m app.ingest app/fixtures/places.jsonl   # seed from fixtures

Uses the configured providers (env), so VECTOR_STORE_PROVIDER=qdrant writes to
Qdrant and =memory is a dry-run (nothing persists across processes).
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

from app.config import get_settings
from app.providers import build_providers
from app.services.ingest import ingest_records


async def _run(path: pathlib.Path) -> int:
    settings = get_settings()
    providers = build_providers(settings)
    with path.open() as fh:
        report = await ingest_records(fh, providers)
    print(report.model_dump_json(indent=2))
    return 0 if report.failed == 0 else 1


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.ingest <places.jsonl>", file=sys.stderr)
        raise SystemExit(2)
    path = pathlib.Path(sys.argv[1])
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_run(path)))


if __name__ == "__main__":
    main()
