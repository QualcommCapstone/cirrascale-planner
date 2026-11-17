import json

import pytest

from app.config import Settings
from app.fixtures import load_fixture_places
from app.providers import UpsertItem, VectorSpaceMismatch, build_providers
from app.providers.embedding import CirrascaleEmbeddingProvider, MockEmbeddingProvider
from app.providers.llm import MockLLMProvider
from app.providers.vector_store import InMemoryVectorStore
from app.schemas.place import SearchFilters

# --- embeddings ---

async def test_mock_embeddings_are_deterministic_and_sized():
    emb = MockEmbeddingProvider(dim=128)
    a = await emb.embed_query("Fushimi Inari")
    b = await emb.embed_query("Fushimi Inari")
    c = await emb.embed_query("Nishiki Market")
    assert len(a) == 128
    assert a == b          # repeatable
    assert a != c          # different text -> different vector
    docs = await emb.embed_documents(["x", "y"])
    assert len(docs) == 2 and all(len(v) == 128 for v in docs)


async def test_cirrascale_embedding_is_adapter_stub():
    emb = CirrascaleEmbeddingProvider(Settings(cirrascale_embedding_model=None))
    with pytest.raises(RuntimeError):
        await emb.embed_query("x")


# --- vector store ---

async def _seed_store(dim: int = 64) -> InMemoryVectorStore:
    emb = MockEmbeddingProvider(dim=dim)
    store = InMemoryVectorStore(dim=emb.dim, model_version=emb.model_version)
    places = load_fixture_places()
    vectors = await emb.embed_documents([p.embedding_text() for p in places])
    await store.upsert_places([UpsertItem(p, v) for p, v in zip(places, vectors, strict=True)])
    return store


async def test_in_memory_search_ranks_and_filters():
    store = await _seed_store()
    emb = MockEmbeddingProvider(dim=64)
    q = await emb.embed_query("Kyoto bamboo")
    results = await store.search(q, limit=3)
    assert 1 <= len(results) <= 3
    assert results == sorted(results, key=lambda r: r.score, reverse=True)

    kyoto = await store.search(q, filters=SearchFilters(city="Kyoto"), limit=10)
    assert all(r.place.city == "Kyoto" for r in kyoto)

    food = await store.search(q, filters=SearchFilters(categories=["food"]), limit=10)
    assert all(r.place.category == "food" for r in food)


async def test_vector_dim_mismatch_rejected():
    store = InMemoryVectorStore(dim=64, model_version="mock-v1-64")
    with pytest.raises(VectorSpaceMismatch):
        await store.search([0.0] * 32)


# --- llm ---

async def test_mock_llm_returns_valid_outline_and_days():
    llm = MockLLMProvider()
    outline = json.loads(await llm.generate('return {"stops": ...}'))
    assert outline["stops"] and outline["legs"]

    days = json.loads(await llm.generate('plan days 1-3 as {"days": ...}'))
    assert [d["day"] for d in days["days"]] == [1, 2, 3]
    assert days["days"][0]["morning"]["name"]


# --- factory ---

def test_factory_mock_mode_is_consistent():
    providers = build_providers(Settings())  # defaults: mock/memory/mock
    assert isinstance(providers.embedding, MockEmbeddingProvider)
    assert isinstance(providers.vector_store, InMemoryVectorStore)
    assert isinstance(providers.llm, MockLLMProvider)
    # store inherits the embedder's space
    assert providers.vector_store.dim == providers.embedding.dim
    assert providers.vector_store.model_version == providers.embedding.model_version
