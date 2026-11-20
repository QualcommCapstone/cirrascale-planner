"""Vector stores: in-memory (tests/mock) and Qdrant (real)."""

from __future__ import annotations

import math
import uuid

from app.config import Settings
from app.providers.base import UpsertItem, VectorSpaceMismatch
from app.schemas.place import Place, SearchFilters, SearchResult

# Fixed namespace so a place id always maps to the same Qdrant point id.
_NAMESPACE = uuid.UUID("7b1f6e1e-1234-4000-8000-000000000001")


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _matches(place: Place, f: SearchFilters | None) -> bool:
    if not f:
        return True
    if f.city and place.city.lower() != f.city.lower():
        return False
    if f.country and place.country.lower() != f.country.lower():
        return False
    if f.categories and place.category not in f.categories:
        return False
    return True


class InMemoryVectorStore:
    """Cosine-similarity store for tests. Rejects dimension mismatches."""

    def __init__(self, dim: int, model_version: str) -> None:
        self._dim = dim
        self._model_version = model_version
        self._items: dict[str, tuple[list[float], Place]] = {}

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._model_version

    def _check(self, vector: list[float]) -> None:
        if len(vector) != self._dim:
            raise VectorSpaceMismatch(
                f"vector dim {len(vector)} != store dim {self._dim}"
            )

    async def upsert_places(self, items: list[UpsertItem]) -> int:
        for item in items:
            self._check(item.vector)
            self._items[item.place.id] = (item.vector, item.place)
        return len(items)

    async def search(
        self, vector: list[float], filters: SearchFilters | None = None, limit: int = 10
    ) -> list[SearchResult]:
        self._check(vector)
        scored = [
            SearchResult(place=place, score=_cosine(vector, vec))
            for vec, place in self._items.values()
            if _matches(place, filters)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]


class QdrantVectorStore:
    """Qdrant-backed store. Collection is created lazily with the configured
    dimension. Point ids are UUIDv5 of the place id, so re-ingestion is idempotent.
    The model version is written into every payload to keep vector spaces honest."""

    def __init__(self, settings: Settings, dim: int, model_version: str) -> None:
        from qdrant_client import AsyncQdrantClient

        self._settings = settings
        self._dim = dim
        self._model_version = model_version
        self._collection = settings.qdrant_collection
        self._client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        self._ready = False

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def model_version(self) -> str:
        return self._model_version

    async def _ensure(self) -> None:
        if self._ready:
            return
        from qdrant_client import models

        exists = await self._client.collection_exists(self._collection)
        if not exists:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=models.VectorParams(size=self._dim, distance=models.Distance.COSINE),
            )
        self._ready = True

    async def upsert_places(self, items: list[UpsertItem]) -> int:
        from qdrant_client import models

        await self._ensure()
        points = []
        for item in items:
            if len(item.vector) != self._dim:
                raise VectorSpaceMismatch(
                    f"vector dim {len(item.vector)} != store dim {self._dim}"
                )
            payload = item.place.model_dump(mode="json")
            payload["model_version"] = self._model_version
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid5(_NAMESPACE, item.place.id)),
                    vector=item.vector,
                    payload=payload,
                )
            )
        await self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    async def search(
        self, vector: list[float], filters: SearchFilters | None = None, limit: int = 10
    ) -> list[SearchResult]:
        from qdrant_client import models

        await self._ensure()
        if len(vector) != self._dim:
            raise VectorSpaceMismatch(f"vector dim {len(vector)} != store dim {self._dim}")

        conditions = [
            models.FieldCondition(key="model_version", match=models.MatchValue(value=self._model_version))
        ]
        if filters:
            if filters.city:
                conditions.append(models.FieldCondition(key="city", match=models.MatchValue(value=filters.city)))
            if filters.country:
                conditions.append(
                    models.FieldCondition(key="country", match=models.MatchValue(value=filters.country))
                )
            if filters.categories:
                conditions.append(
                    models.FieldCondition(key="category", match=models.MatchAny(any=list(filters.categories)))
                )

        # qdrant-client >= 1.10 replaced .search() with the universal
        # .query_points(); the response carries the hits under .points.
        response = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            query_filter=models.Filter(must=conditions),
            limit=limit,
            with_payload=True,
        )
        results: list[SearchResult] = []
        for h in response.points:
            payload = dict(h.payload or {})
            payload.pop("model_version", None)
            results.append(SearchResult(place=Place.model_validate(payload), score=float(h.score)))
        return results
