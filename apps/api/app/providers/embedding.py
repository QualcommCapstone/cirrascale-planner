"""Embedding providers."""

from __future__ import annotations

import math
import random

from app.config import Settings


class MockEmbeddingProvider:
    """Deterministic, dimensionally-consistent embeddings for tests and mock mode.

    Same text -> same unit vector, every run. Not semantically meaningful; just
    stable and the right shape so the whole pipeline is exercisable offline.
    """

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return f"mock-v1-{self._dim}"

    def _vector(self, text: str) -> list[float]:
        rng = random.Random(f"{self.model_version}:{text}")
        v = [rng.uniform(-1.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class CirrascaleEmbeddingProvider:
    """Adapter for the Cirrascale-hosted embedding model.

    The model id, endpoint path and response format are **not confirmed yet**, so
    the methods raise until configured. When the service is available, set
    CIRRASCALE_EMBEDDING_MODEL and implement the httpx call here — nothing else in
    the pipeline needs to change (it depends only on the EmbeddingProvider shape).
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        # Dimension is model-defined; configured once known.
        self._dim = settings.vector_dim

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._settings.cirrascale_embedding_model or "cirrascale-unconfigured"

    def _not_ready(self) -> RuntimeError:
        return RuntimeError(
            "Cirrascale embedding endpoint/format is not confirmed yet. "
            "Set CIRRASCALE_EMBEDDING_MODEL and implement the call in "
            "CirrascaleEmbeddingProvider, or run with EMBEDDING_PROVIDER=mock."
        )

    async def embed_query(self, text: str) -> list[float]:
        raise self._not_ready()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise self._not_ready()
