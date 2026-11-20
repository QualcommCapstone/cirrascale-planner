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


async def test_cirrascale_embedding_requires_a_key():
    emb = CirrascaleEmbeddingProvider(Settings(_env_file=None, cirrascale_api_key=None))
    with pytest.raises(RuntimeError, match="CIRRASCALE_API_KEY"):
        await emb.embed_query("x")


async def test_cirrascale_embedding_calls_openai_style_endpoint():
    """No real network: a MockTransport returns BGE-shaped responses."""
    import httpx

    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured.append({"url": str(request.url), "body": body})
        inputs = body["input"]
        data = [{"embedding": [0.01] * 768, "index": i} for i in range(len(inputs))]
        return httpx.Response(200, json={"data": data, "model": body["model"]})

    client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))
    settings = Settings(
        _env_file=None,
        cirrascale_api_key="k",
        cirrascale_embedding_model="BAAI/bge-base-en-v1.5",
        embedding_query_instruction="PFX: ",  # configured instruction is applied to queries
    )
    emb = CirrascaleEmbeddingProvider(settings, client=client)

    assert emb.dim == 768                       # dimension fixed by the model
    assert emb.model_version == "BAAI/bge-base-en-v1.5"

    q = await emb.embed_query("tokyo temple")
    assert len(q) == 768
    assert captured[-1]["url"].endswith("/embeddings")
    assert captured[-1]["body"]["input"][0] == "PFX: tokyo temple"  # instruction on the query

    docs = await emb.embed_documents(["a", "b", "c"])
    assert len(docs) == 3 and all(len(v) == 768 for v in docs)
    assert captured[-1]["body"]["input"] == ["a", "b", "c"]  # documents: never instructed
    await emb.aclose()


async def test_embedding_query_instruction_off_by_default():
    import httpx

    seen: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        inp = json.loads(request.content)["input"]
        seen.append(inp)
        return httpx.Response(200, json={"data": [{"embedding": [0.0] * 768, "index": 0}]})

    client = httpx.AsyncClient(base_url="http://test", transport=httpx.MockTransport(handler))
    emb = CirrascaleEmbeddingProvider(
        Settings(_env_file=None, cirrascale_api_key="k", cirrascale_embedding_model="BAAI/bge-base-en-v1.5"),
        client=client,
    )
    await emb.embed_query("tokyo temple")
    assert seen[-1] == ["tokyo temple"]  # no instruction by default
    await emb.aclose()


def test_large_model_dimension():
    emb = CirrascaleEmbeddingProvider(
        Settings(_env_file=None, cirrascale_api_key="k", cirrascale_embedding_model="BAAI/bge-large-en-v1.5")
    )
    assert emb.dim == 1024


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
