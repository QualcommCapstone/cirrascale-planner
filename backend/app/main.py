"""FastAPI entry point.

Run locally:  uv run uvicorn app.main:app --reload   ->  http://localhost:8000/docs

Only a health check for now. Data routes (places, verification) are added in
later steps as each piece is built.
"""

from fastapi import FastAPI

app = FastAPI(title="AI100 Travel Planner backend", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
