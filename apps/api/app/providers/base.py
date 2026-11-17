"""Provider interfaces. Implementations (mock + real) are interchangeable via
config, so switching to the real Cirrascale embedding or Qdrant is an env change,
never a code change.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.schemas.place import Place, SearchFilters, SearchResult


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Turns text into vectors. `model_version` guards the vector space: vectors
    from different models/dimensions must never be mixed in one collection."""

    @property
    def dim(self) -> int: ...

    @property
    def model_version(self) -> str: ...

    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class UpsertItem:
    """A place plus its vector, ready for the store."""

    __slots__ = ("place", "vector")

    def __init__(self, place: Place, vector: list[float]) -> None:
        self.place = place
        self.vector = vector


@runtime_checkable
class VectorStore(Protocol):
    @property
    def dim(self) -> int: ...

    @property
    def model_version(self) -> str: ...

    async def upsert_places(self, items: list[UpsertItem]) -> int: ...

    async def search(
        self,
        vector: list[float],
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchResult]: ...


@runtime_checkable
class LLMProvider(Protocol):
    """Generic completion. The RAG service builds the prompt and parses the text;
    the provider only transports it. Keeps mock/real symmetric."""

    async def generate(self, prompt: str, *, max_tokens: int = 1024) -> str: ...


class VectorSpaceMismatch(RuntimeError):
    """Raised when a vector's dimension or model version does not match the store."""
