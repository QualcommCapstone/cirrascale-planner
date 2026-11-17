"""FastAPI application: CORS, request ids, structured logging, consistent errors."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging import configure_logging, request_id_var
from app.routers import health, v1

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("api")

app = FastAPI(
    title="Cirrascale Planner API",
    version="0.1.0",
    summary="Travel planning backend (RAG over Qdrant + Cirrascale AI100).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id, time the request, and log one structured line."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(rid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error", extra={"extra_fields": {"path": request.url.path}})
        response = JSONResponse(
            status_code=500,
            content={"error": "Internal server error.", "request_id": rid},
        )
    finally:
        request_id_var.reset(token)
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    response.headers["x-request-id"] = rid
    logger.info(
        "request",
        extra={
            "extra_fields": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "ms": duration_ms,
            }
        },
    )
    return response


app.include_router(health.router)
app.include_router(v1.router)
