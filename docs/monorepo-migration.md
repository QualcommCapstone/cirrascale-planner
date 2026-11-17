# Monorepo Migration

> How and why the repo became a monorepo, and the decisions behind it. Pair with
> `BACKEND-PROGRESS.md` (live status) and `docs/architecture.md`.

## Why

Transitioning from a frontend-centric Next.js app to a modular full-stack platform:

```
User → Next.js (apps/web) → FastAPI (apps/api) → Query Embedding → Qdrant
     → Context → Cirrascale AI100 LLM → Validated Itinerary → Next.js
```

A separate developer builds the scraper (DuckDuckGo → Scrapy → cleaning → JSONL).
This migration prepares the structure and builds the backend with **mock
providers**, so nothing waits on the embedding model or the scraper.

## Layout

```
apps/web/          the existing Next.js app (moved here, history preserved)
apps/api/          FastAPI backend (Python 3.11, uv)
packages/contracts/ generated TypeScript types from the backend OpenAPI schema
infra/             docker-compose (Qdrant + api) and local-dev infra
docs/              shared docs (stayed at repo root)
```

Not created here: a top-level `scraper/` — the teammate's scraper lives on
branches `backend/scraper` and `backend/clean-data-model` and is **not touched**.
The backend defines a JSONL **ingestion contract** that their output will satisfy.

## Decisions (confirmed)

1. **npm workspaces**, not pnpm. pnpm isn't installed and the frontend's
   dependency tree (OpenUI + peers `zustand@4`, `zod@4`, `ai`, `three`,
   `react-globe.gl`) was hand-resolved under npm; pnpm's strict resolution would
   likely re-break it. The prompt allows this when pnpm is risky.
2. **Branch `feature/backend-monorepo` off `feature/itinerary-globe-ui`** (the
   current frontend, incl. Drew's redesign) — not `main` (far behind). Final PR
   targets `main` after frontend PR #6 merges; rebase + re-verify then.
3. **Canonical API contract = the existing `Trip`/`Stop`/`Activity` model + NDJSON
   streaming.** FastAPI mirrors the Zod schemas in Pydantic, accepts
   `{goal, preferences}`, preserves `outline → stop×N → done`, and keeps Wikipedia
   place verification/photos/sources. The simpler `{destination, days, budget,
   currency, preferences}` is an optional adapter. Next's `/api/itinerary` becomes
   a streaming **compat proxy** to FastAPI. TS types are generated from OpenAPI and
   checked against the Zod schemas.

## What moved

`git mv` into `apps/web/`: `src/`, `public/`, `package.json`, `next.config.mjs`,
`tsconfig.json`, `tailwind.config.ts`, `postcss.config.mjs`, `components.json`,
`.eslintrc.json`, `vitest.config.ts`, `.env.example`. The old root
`package-lock.json` was removed; a single workspace lockfile is regenerated at the
root by `npm install`.

Because every tool config (`tsconfig`, `tailwind`, `vitest`, `postcss`) lives
inside `apps/web/` and uses paths relative to it, the `@/*` alias and content
globs keep working unchanged — and the untracked local `qualcomm_test/` scaffold
at the repo root now falls outside `apps/web`'s config (it previously broke a
local `tsc`; CI was never affected).

## Root scripts

```bash
npm install          # installs all workspaces
npm run dev:web      # next dev        (apps/web)
npm run build:web    # next build      (apps/web)
npm run lint:web     # next lint       (apps/web)
npm run test:web     # vitest          (apps/web)
npm run test:api     # pytest          (apps/api)
```

## Baseline (pre-migration, recorded)

- App **compiles successfully**; **110/110** Vitest tests pass; **lint clean**.
- The only `npm run build` failure was the untracked `qualcomm_test/` scaffold
  (`@/agent` missing) — local-only, resolved by the move.

## CI

`.github/workflows/ci.yml`: a `web` job (`npm ci` → `lint:web` → `test:web` →
`build:web`) and, added with the backend, an `api` job (uv → ruff → pytest in
mock mode, no real Cirrascale/Qdrant).
