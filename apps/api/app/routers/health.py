"""Liveness (/health) and readiness (/ready)."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Process is up. No dependency checks, safe for load-balancer liveness."""
    return {"status": "ok", "service": "cirrascale-planner-api"}


@router.get("/ready")
async def ready() -> dict:
    """Dependency readiness. Reports provider *names* and per-dependency status
    only — never URLs, keys, or other infrastructure detail."""
    s = get_settings()

    checks = {
        "embedding": "ok",  # mock is always ready; real check added with the provider
        "vector_store": "ok",
        "llm": "ok",
    }
    if s.llm_provider == "cirrascale" and not s.has_cirrascale_key:
        checks["llm"] = "missing_credentials"
    if s.embedding_provider == "cirrascale" and not s.has_cirrascale_key:
        checks["embedding"] = "missing_credentials"

    ready = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if ready else "degraded",
        "providers": {
            "embedding": s.embedding_provider,
            "vector_store": s.vector_store_provider,
            "llm": s.llm_provider,
        },
        "checks": checks,
    }
