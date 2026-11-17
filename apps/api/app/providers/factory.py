"""Build the configured providers. Switching mock <-> real is env-only."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.providers.base import EmbeddingProvider, LLMProvider, VectorStore
from app.providers.embedding import CirrascaleEmbeddingProvider, MockEmbeddingProvider
from app.providers.llm import CirrascaleLLMProvider, MockLLMProvider
from app.providers.vector_store import InMemoryVectorStore, QdrantVectorStore


def make_embedding(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "cirrascale":
        return CirrascaleEmbeddingProvider(settings)
    return MockEmbeddingProvider(dim=settings.vector_dim)


def make_vector_store(settings: Settings, embedding: EmbeddingProvider) -> VectorStore:
    # The store inherits the embedder's dimension + version so a collection can
    # never silently hold vectors from a different model/space.
    if settings.vector_store_provider == "qdrant":
        return QdrantVectorStore(settings, dim=embedding.dim, model_version=embedding.model_version)
    return InMemoryVectorStore(dim=embedding.dim, model_version=embedding.model_version)


def make_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "cirrascale":
        return CirrascaleLLMProvider(settings)
    return MockLLMProvider()


@dataclass
class Providers:
    embedding: EmbeddingProvider
    vector_store: VectorStore
    llm: LLMProvider


def build_providers(settings: Settings) -> Providers:
    embedding = make_embedding(settings)
    return Providers(
        embedding=embedding,
        vector_store=make_vector_store(settings, embedding),
        llm=make_llm(settings),
    )
