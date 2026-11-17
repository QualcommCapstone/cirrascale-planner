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
3. [x] API contracts (Pydantic mirror of Trip; OpenAPI → packages/contracts TS)
4. [x] Provider interfaces + mocks (embedding, vector store, LLM)
5. [x] RAG orchestration (validate → embed → search → context → LLM → validate → stream)
6. [x] Frontend integration (Next /api/itinerary proxy to FastAPI; configurable URL)
7. [x] Ingestion CLI + tests + docker-compose + docs

## Status log
- Stage 1 (323848b): monorepo migration — web → apps/web (R100 renames), root
  workspace, CI web job, gitignore, docs. Verified: lint/110 tests/build all pass.
- Stage 2 (pending commit): FastAPI foundation in apps/api (uv, Python 3.11).
  `/health`, `/ready` (provider status, no secrets), `/api/v1/plan|chat` 501
  stubs, pydantic-settings config, CORS, structured JSON logging + request ids.
  CI `api` job added (uv → ruff → pytest, mock mode). Verified: ruff clean, 4
  pytest pass. Next: Stage 3 contracts (Pydantic mirror of Trip + OpenAPI→TS).
- Stage 3 (pending commit): canonical contracts. `apps/api/app/schemas/trip.py`
  mirrors the Zod Trip/Stop/Activity model 1:1 (camelCase preserved) + TripEvent,
  SimplePlanRequest adapter, ChatRequest. `scripts/export_openapi.py` dumps a
  complete OpenAPI; `packages/contracts` turns it into TS (`openapi-typescript`),
  re-exported with friendly names. Regression: `contract-check.ts` (compile-time
  gate — WebTrip must satisfy the generated contract), web vitest + api pytest on
  a shared `sample-trip.json`. Regenerate with `npm run contracts:generate`.
  Verified: api 9 pytest, web 113 vitest. Next: Stage 4 providers + mocks.
- Stage 4 (pending commit): provider abstractions in app/providers/. Protocols in
  base.py; Mock + Cirrascale-adapter embedding (deterministic unit vectors; real
  endpoint stubbed — unconfirmed), InMemory + Qdrant vector stores (cosine +
  filters; dim/model_version guard so spaces can't mix; UUIDv5 ids = idempotent),
  Mock + Cirrascale LLM (httpx pooling/timeout/retries, reuses completions config).
  factory.build_providers() selects from env. Schema app/schemas/place.py + a
  labeled synthetic fixtures/places.jsonl. Verified: ruff clean, 15 pytest.
  Next: Stage 5 RAG orchestration (validate→embed→search→context→LLM→validate→stream).
- Stage 5 (pending commit): RAG planning in app/services/. rag.generate_trip()
  streams NDJSON (outline → stop×N → done); plan_trip() assembles a full Trip
  (chat/tests). prompts.py (grounded outline + per-stop days, with a
  [source:id] context block), parsing.extract_json, normalize.py (lenient parse +
  ground each activity against retrieved places → verified/sourceUrl, coords from
  the place; invented places flagged not trusted), totals.estimate_total_usd (in
  the done event). /api/v1/plan streams via a queue bridge (no buffering);
  /api/v1/chat re-plans around the instruction. main.py lifespan builds providers
  + seeds the in-memory store from fixtures. DoneEvent gained optional
  estimatedCostUsd → contracts regenerated. Verified: api 19 pytest, ruff clean.
  Next: Stage 6 frontend integration (Next /api/itinerary proxy to FastAPI).
- Stage 6 (pending commit): frontend integration. src/lib/backend.ts
  (getBackendUrl, server-only). /api/itinerary: if BACKEND_URL set, proxy-stream
  from FastAPI /api/v1/plan (no buffering); else the existing in-Next Cirrascale +
  Wikipedia pipeline (unchanged, not removed). Same TripEvent NDJSON both ways, so
  the UI is untouched. .env.example documents BACKEND_URL. Tests: proxy.test.ts
  (proxy path, 502 on unreachable, 400 on bad body). Verified: web 116 vitest +
  build; live uvicorn smoke: /health, /ready, /api/v1/plan streams
  outline→stop→done. Next: Stage 7 tests + docker-compose + docs.
- Stage 7: ingestion + infra + docs. app/services/ingest.py +
  `python -m app.ingest <jsonl>` (validate → batch-embed → upsert, idempotent,
  reports ok/failed; never in /plan). infra/docker-compose.yml (Qdrant + API) +
  apps/api/Dockerfile (uv, non-root, HEALTHCHECK). Qdrant integration test
  auto-skips without Qdrant. Docs: api-contract, local-development,
  cirrascale-integration; architecture + AGENTS updated. Verified: api 21 pytest
  + 1 skipped, ruff clean, compose valid.

## ALL 7 STAGES COMPLETE — mock mode works end-to-end.

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
