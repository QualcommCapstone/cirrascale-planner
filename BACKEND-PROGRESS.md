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
1. [ ] Monorepo migration (move web → apps/web, workspaces, CI, gitignore, docs)
2. [ ] FastAPI foundation (/health, /ready, /api/v1/plan, /api/v1/chat, config, CORS, logging)
3. [ ] API contracts (Pydantic mirror of Trip; OpenAPI → packages/contracts TS)
4. [ ] Provider interfaces + mocks (embedding, vector store, LLM)
5. [ ] RAG orchestration (validate → embed → search → context → LLM → validate → stream)
6. [ ] Frontend integration (Next /api/itinerary proxy to FastAPI; configurable URL)
7. [ ] Tests + docker-compose + docs

## Status log
- (in progress) Stage 1: moved the Next app into `apps/web/` with `git mv`,
  added root workspace `package.json`, rewrote `.gitignore`, updated CI to a
  web workspace job, wrote `docs/monorepo-migration.md`. Verifying build/lint/test
  from `apps/web` next, then commit.

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
