# Local Development

Monorepo (npm workspaces + a uv-managed Python backend). Everything runs in
**mock mode** by default — no Cirrascale key, no embedding model, no Qdrant needed.

## Prerequisites

- Node 20+ and npm
- [uv](https://docs.astral.sh/uv/) (Python 3.11 is provisioned by uv)
- Docker (only for Qdrant / container runs)

## Install

```bash
npm install                       # all JS workspaces (apps/web, packages/contracts)
cd apps/api && uv sync --all-extras --dev && cd ../..
```

## Run

```bash
# 1) Backend (mock mode — works offline)
cd apps/api
cp .env.example .env
uv run uvicorn app.main:app --reload       # http://localhost:8000  (/docs for OpenAPI)
cd ../..

# 2) Frontend
cp apps/web/.env.example apps/web/.env.local
#   leave BACKEND_URL unset  -> in-Next pipeline (Cirrascale + Wikipedia)
#   set BACKEND_URL=http://localhost:8000 -> proxy to FastAPI
npm run dev:web                            # http://localhost:3000
```

Optional real vector DB:

```bash
docker compose -f infra/docker-compose.yml up -d qdrant   # Qdrant on :6333
# then run the API with VECTOR_STORE_PROVIDER=qdrant, or the whole stack:
docker compose -f infra/docker-compose.yml up --build
```

## Mock mode

```env
EMBEDDING_PROVIDER=mock      # deterministic vectors
VECTOR_STORE_PROVIDER=memory # in-memory, seeded from labeled fixtures
LLM_PROVIDER=mock            # deterministic itinerary JSON
```

Switching to real services is **config only** — no code changes. The fixtures
(`apps/api/app/fixtures/places.jsonl`) are clearly synthetic, not real
recommendations.

## Checks

```bash
npm run lint:web
npm run test:web                 # vitest
npm run build:web                # also runs the contract compile-time gate
npm run test:api                 # pytest (cd apps/api && uv run pytest)
cd apps/api && uv run ruff check .
npm run contracts:generate       # regenerate TS types from the backend OpenAPI
```

## Root scripts

`npm run` → `dev:web` · `build:web` · `lint:web` · `test:web` · `test:api` ·
`contracts:generate`.
