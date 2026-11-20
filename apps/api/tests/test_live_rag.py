"""Opt-in live integration test: real Cirrascale embeddings + real Qdrant.

Skipped by default (and in CI). Run it against a running stack after ingesting the
Tokyo dataset:

    RUN_LIVE_RAG=1 CIRRASCALE_API_KEY=… QDRANT_COLLECTION=tokyo_dev \
      uv run pytest tests/test_live_rag.py -v

It builds Settings explicitly (not from env) so it ignores the mock providers that
tests/conftest.py forces for the hermetic suite.
"""

from __future__ import annotations

import math
import os

import pytest

from app.config import Settings
from app.providers import build_providers
from app.schemas.place import SearchFilters

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_LIVE_RAG"),
    reason="opt-in live test; set RUN_LIVE_RAG=1 with real Cirrascale + Qdrant",
)


def _live_settings() -> Settings:
    return Settings(
        _env_file=None,
        embedding_provider="cirrascale",
        vector_store_provider="qdrant",
        llm_provider="cirrascale",
        cirrascale_api_key=os.environ.get("CIRRASCALE_API_KEY"),
        cirrascale_embedding_model=os.getenv(
            "CIRRASCALE_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"
        ),
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "tokyo_dev"),
    )


async def test_live_embedding_is_768d_and_finite():
    providers = build_providers(_live_settings())
    try:
        v = await providers.embedding.embed_query("traditional temples in Tokyo")
        assert len(v) == 768  # dimension fixed by bge-base
        assert all(isinstance(x, float) and math.isfinite(x) for x in v)
        # Not the deterministic mock: two different texts differ.
        other = await providers.embedding.embed_query("late-night jazz bars")
        assert v != other
    finally:
        await providers.embedding.aclose()


async def test_live_retrieval_returns_real_grounded_places():
    providers = build_providers(_live_settings())
    try:
        v = await providers.embedding.embed_query("traditional Japanese food and sushi")
        results = await providers.vector_store.search(
            v, SearchFilters(city="Tokyo", country="Japan", categories=["food"]), limit=5
        )
        assert results, "expected grounded Tokyo food places from Qdrant"
        for r in results:
            assert r.place.city == "Tokyo" and r.place.category == "food"  # filters honored
            assert r.place.source_url and r.place.source_attribution  # attribution preserved
            assert 0.0 <= r.score <= 1.0
    finally:
        await providers.embedding.aclose()
