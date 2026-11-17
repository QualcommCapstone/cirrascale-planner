# Backend / Monorepo — Live Progress

> Working checkpoint so any agent can resume without re-auditing. Update after
> every committed stage. Branch: `feature/backend-monorepo` (off
> `feature/itinerary-globe-ui`). Commits authored `RishithMody
> <rishithmody@gmail.com>`, no Claude trailer.

## Decisions
npm workspaces · canonical = existing Trip model + NDJSON streaming · FastAPI
mirrors Zod→Pydantic · Next `/api/itinerary` becomes a streaming proxy to FastAPI
· mock providers (embedding/vector/LLM) until Cirrascale embedding ships · do NOT
touch the scraper (teammate branches `backend/scraper`, `backend/clean-data-model`).
See `docs/monorepo-migration.md`.

## Staged commits (plan)
1. [x] Monorepo migration (move web → apps/web, workspaces, CI, gitignore, docs) — 323848b
2. [x] FastAPI foundation (/health, /ready, /api/v1/plan+chat stubs, config, CORS, request-id logging)
3. [ ] API contracts (Pydantic mirror of Trip; OpenAPI → packages/contracts TS)
4. [ ] Provider interfaces + mocks (embedding, vector store, LLM)
5. [ ] RAG orchestration (validate → embed → search → context → LLM → validate → stream)
6. [ ] Frontend integration (Next /api/itinerary proxy to FastAPI; configurable URL)
7. [ ] Tests + docker-compose + docs

## Status log
- Stage 1 (323848b): monorepo migration — web → apps/web (R100 renames), root
  workspace, CI web job, gitignore, docs. Verified: lint/110 tests/build all pass.
- Stage 2 (pending commit): FastAPI foundation in apps/api (uv, Python 3.11).
  `/health`, `/ready` (provider status, no secrets), `/api/v1/plan|chat` 501
  stubs, pydantic-settings config, CORS, structured JSON logging + request ids.
  CI `api` job added (uv → ruff → pytest, mock mode). Verified: ruff clean, 4
  pytest pass. Next: Stage 3 contracts (Pydantic mirror of Trip + OpenAPI→TS).

## Run it (updated each stage)
```bash
npm install
npm run dev:web        # http://localhost:3000
npm run test:web
# backend (once stage 2 lands):
# docker compose -f infra/docker-compose.yml up -d
# cd apps/api && uv run uvicorn app.main:app --reload
```

## Known issues / watch-outs
- Untracked local-only dirs at repo root (`qualcomm_test/`, `.agents/`,
  `.claude/skills/openui/`, `skills-lock.json`) are now gitignored; never commit.
- `Llama-3.1-70B` → 429 on the Cirrascale free tier; default is `Llama-3.1-8B`.
- Real Cirrascale/Qdrant calls must never run in automated unit tests (mock only).
