"""v1 API. Full request/response contracts and the RAG planning service are
wired in later stages (contracts, providers, RAG). These endpoints exist now so
the surface and CORS/observability are testable from the start."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1", tags=["planning"])

_PENDING = JSONResponse(
    status_code=501,
    content={"error": "Not implemented yet — mock RAG planning lands in a later stage."},
)


@router.post("/plan")
async def plan() -> JSONResponse:
    return _PENDING


@router.post("/chat")
async def chat() -> JSONResponse:
    return _PENDING
