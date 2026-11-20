"""Embedding providers."""

from __future__ import annotations

import asyncio
import math
import random

import httpx

from app.config import Settings

# Output dimension per Cirrascale-hosted embedding model, so the vector store is
# created with the matching size before any call is made.
EMBEDDING_MODEL_DIMS = {
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
}
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

# BGE v1.5 retrieval wants a short instruction prepended to the QUERY only
# (documents are embedded as-is). https://huggingface.co/BAAI/bge-base-en-v1.5
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


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
    """Real embeddings via the Qualcomm AI Inference Suite (OpenAI-compatible).

        POST {base}/embeddings  {"input": str | list[str], "model": "<id>"}
        -> {"data": [{"embedding": [...], "index": 0}, ...], "usage": {...}}

    Default model BAAI/bge-base-en-v1.5 (768-dim; large is 1024). The dimension is
    fixed by the model and exposed before any call so the vector store matches.
    Key stays server-side. `client` is injectable for tests.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._model = settings.cirrascale_embedding_model or DEFAULT_EMBEDDING_MODEL
        self._dim = EMBEDDING_MODEL_DIMS.get(self._model, settings.vector_dim)
        self._batch = max(1, settings.embedding_batch_size)
        # Optional query-only instruction (default off — the hosted BGE scored
        # worse with the BGE_QUERY_INSTRUCTION; set EMBEDDING_QUERY_INSTRUCTION to override).
        self._query_instruction = settings.embedding_query_instruction
        self._client = client or httpx.AsyncClient(
            base_url=settings.cirrascale_base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={
                "Authorization": f"Bearer {settings.cirrascale_api_key or ''}",
                "Content-Type": "application/json",
            },
        )

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._model

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        if not self._settings.cirrascale_api_key:
            raise RuntimeError("CIRRASCALE_API_KEY is not set.")
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.post(
                    "/embeddings", json={"input": inputs, "model": self._model}
                )
                resp.raise_for_status()
                data = resp.json().get("data") or []
                data = sorted(data, key=lambda d: d.get("index", 0))
                vectors = [d["embedding"] for d in data]
                if len(vectors) != len(inputs):
                    raise RuntimeError(
                        f"embedding count {len(vectors)} != inputs {len(inputs)}"
                    )
                return vectors
            except (httpx.HTTPError, KeyError, RuntimeError) as err:
                last_err = err
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"Cirrascale embeddings failed after retries: {last_err}")

    async def embed_query(self, text: str) -> list[float]:
        vectors = await self._embed([self._query_instruction + text])
        return vectors[0]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            out.extend(await self._embed(texts[i : i + self._batch]))
        return out

    async def aclose(self) -> None:
        await self._client.aclose()
