# apps/api — Cirrascale Planner backend

FastAPI backend (Python 3.11, [uv](https://docs.astral.sh/uv/)). Runs in **mock
mode** by default — no Cirrascale key or Qdrant needed.

## Run

```bash
cd apps/api
cp .env.example .env            # defaults are mock mode
uv sync --all-extras --dev
uv run uvicorn app.main:app --reload   # http://localhost:8000
```

Docs (OpenAPI): http://localhost:8000/docs

## Endpoints

| Method | Path            | Purpose                                             |
| ------ | --------------- | --------------------------------------------------- |
| GET    | `/health`       | Liveness — process is up.                            |
| GET    | `/ready`        | Readiness — provider names + per-dependency status. |
| POST   | `/api/v1/plan`  | Generate an itinerary (RAG). *Wired in a later stage.* |
| POST   | `/api/v1/chat`  | Modify an itinerary via chat. *Wired in a later stage.* |

## Config

All via env (`app/config.py`, pydantic-settings). Provider selectors:
`EMBEDDING_PROVIDER`, `VECTOR_STORE_PROVIDER`, `LLM_PROVIDER` (`mock`/`memory`
defaults). Secrets are server-only. See `.env.example`.

## Test

```bash
uv run pytest -q          # mock providers only; no real Cirrascale/Qdrant calls
uv run ruff check .
```
