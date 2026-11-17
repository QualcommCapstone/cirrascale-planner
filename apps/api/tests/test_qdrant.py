"""Qdrant integration test. Skips unless a Qdrant is reachable at QDRANT_URL,
so it never blocks unit CI; run it with `docker compose -f infra/docker-compose.yml up -d qdrant`.
"""

import socket
from urllib.parse import urlparse

import pytest

from app.config import Settings
from app.fixtures import load_fixture_places
from app.providers import UpsertItem
from app.providers.embedding import MockEmbeddingProvider
from app.providers.vector_store import QdrantVectorStore
from app.schemas.place import SearchFilters


def _qdrant_up(url: str) -> bool:
    parsed = urlparse(url)
    host, port = parsed.hostname or "localhost", parsed.port or 6333
    try:
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except OSError:
        return False


settings = Settings()
pytestmark = pytest.mark.skipif(
    not _qdrant_up(settings.qdrant_url), reason="Qdrant not reachable at QDRANT_URL"
)


async def test_qdrant_upsert_and_search():
    emb = MockEmbeddingProvider(dim=64)
    store = QdrantVectorStore(
        Settings(qdrant_collection="places_test"), dim=emb.dim, model_version=emb.model_version
    )
    places = load_fixture_places()
    vectors = await emb.embed_documents([p.embedding_text() for p in places])
    n = await store.upsert_places([UpsertItem(p, v) for p, v in zip(places, vectors, strict=True)])
    assert n == len(places)

    q = await emb.embed_query("Kyoto bamboo grove")
    results = await store.search(q, filters=SearchFilters(city="Kyoto"), limit=5)
    assert results
    assert all(r.place.city == "Kyoto" for r in results)
