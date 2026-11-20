"""Live pipeline monitor: a dashboard + data endpoints showing the data flow
(scraped places → embeddings → Qdrant → Cirrascale LLM) in real time.

Served from the backend itself so it is same-origin with the API (no CORS). The
dashboard polls /stats for totals and subscribes to /stream (SSE) for live events;
/demo-embed re-embeds a few real indexed places on demand to show the conversion,
without writing anything back to Qdrant.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from app.config import get_settings
from app.schemas.place import Place
from app.services import monitor

router = APIRouter(tags=["monitor"])

_DASHBOARD_HTML = (Path(__file__).parent / "monitor_dashboard.html").read_text(encoding="utf-8")

# Category breakdown is derived by scrolling the collection; cache it (it only
# changes on re-ingest) so the 4s dashboard poll stays cheap.
_cat_cache: dict[str, int] = {}
_cat_cache_ts = 0.0


async def _category_counts(client: httpx.AsyncClient, url: str, col: str) -> dict[str, int]:
    global _cat_cache, _cat_cache_ts
    if _cat_cache and (time.time() - _cat_cache_ts) < 60:
        return _cat_cache
    counts: dict[str, int] = {}
    offset = None
    for _ in range(50):  # safety bound (50 * 500 = 25k points)
        body: dict = {"limit": 500, "with_payload": ["category"], "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        r = await client.post(f"{url}/collections/{col}/points/scroll", json=body)
        res = r.json().get("result", {})
        for p in res.get("points", []):
            cat = (p.get("payload") or {}).get("category")
            if cat:
                counts[cat] = counts.get(cat, 0) + 1
        offset = res.get("next_page_offset")
        if offset is None:
            break
    _cat_cache, _cat_cache_ts = dict(sorted(counts.items(), key=lambda kv: -kv[1])), time.time()
    return _cat_cache


async def _dataset_stats() -> dict:
    """Best-effort corpus stats straight from the vector store."""
    s = get_settings()
    out: dict = {
        "store": s.vector_store_provider,
        "collection": s.qdrant_collection,
        "points": None,
        "dim": None,
        "distance": None,
        "model": s.cirrascale_embedding_model,
        "categories": {},
    }
    if s.vector_store_provider != "qdrant":
        return out
    url = s.qdrant_url.rstrip("/")
    col = s.qdrant_collection
    async with httpx.AsyncClient(timeout=5.0) as c:
        try:
            r = await c.get(f"{url}/collections/{col}")
            j = r.json()["result"]
            out["points"] = j["points_count"]
            v = j["config"]["params"]["vectors"]
            out["dim"] = v["size"]
            out["distance"] = v["distance"]
        except Exception:
            pass
        try:
            out["categories"] = await _category_counts(c, url, col)
        except Exception:
            pass
        try:
            r = await c.post(
                f"{url}/collections/{col}/points/scroll",
                json={"limit": 1, "with_payload": ["model_version"]},
            )
            pts = r.json()["result"]["points"]
            if pts:
                out["model"] = pts[0]["payload"].get("model_version") or out["model"]
        except Exception:
            pass
    return out


@router.get("/api/v1/monitor/stats")
async def stats() -> dict:
    s = get_settings()
    snap = monitor.snapshot()
    snap["providers"] = {
        "embedding": s.embedding_provider,
        "embedding_model": s.cirrascale_embedding_model,
        "vector_store": s.vector_store_provider,
        "llm": s.llm_provider,
        "llm_model": s.cirrascale_model,
    }
    snap["dataset"] = await _dataset_stats()
    return snap


@router.get("/api/v1/monitor/stream")
async def stream() -> StreamingResponse:
    async def gen():
        q = monitor.add_subscriber()
        yield ": connected\n\n"
        try:
            while True:
                try:
                    evt = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(evt)}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"  # keep the connection warm
        finally:
            monitor.remove_subscriber(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/api/v1/monitor/demo-embed")
async def demo_embed(request: Request) -> dict:
    """Pull a few real indexed places and embed their text live (read-only).

    Shows the scraped-place → embedding-text → embedding-model → vector conversion
    step by step in the event feed. Nothing is written back to Qdrant."""
    s = get_settings()
    providers = request.app.state.providers
    sample: list[Place] = []
    if s.vector_store_provider == "qdrant":
        url = s.qdrant_url.rstrip("/")
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                f"{url}/collections/{s.qdrant_collection}/points/scroll",
                json={"limit": 5, "with_payload": True, "with_vector": False},
            )
            for p in r.json().get("result", {}).get("points", []):
                payload = dict(p.get("payload") or {})
                payload.pop("model_version", None)
                try:
                    sample.append(Place.model_validate(payload))
                except Exception:
                    continue

    monitor.record("request", f"manual embed demo: {len(sample)} scraped places")
    embedded = 0
    for place in sample:
        text = place.embedding_text()
        monitor.record("embed", f"“{place.name}” [{place.category}] → embedding model", text=text[:80])
        vec = await providers.embedding.embed_query(text)
        embedded += 1
        monitor.record(
            "retrieve",
            f"vector ready: {len(vec)}d  [{', '.join(f'{x:+.3f}' for x in vec[:4])} …]",
            dim=len(vec),
        )
    monitor.record("done", f"embedded {embedded} places with {s.cirrascale_embedding_model}")
    return {"embedded": embedded, "model": s.cirrascale_embedding_model}


@router.get("/monitor", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)
