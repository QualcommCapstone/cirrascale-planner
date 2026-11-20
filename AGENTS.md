# AGENTS.md — cirrascale-planner

> **Start here.** This is the entry point for any agent (or human) taking over
> this repo. It links to the steering docs that explain everything else.

## What this is

**cirrascale-planner** is the main platform: a Next.js 14 app that turns a
user's prompt into a structured, step-by-step **plan**. The LLM backend is the
**Qualcomm AI Inference Suite** hosted by **Cirrascale** — our only model
provider.

Sibling repo: **cirrascale-sandbox** — a dependency-light playground for
experimenting with the same API (completions, streaming, scraping + planning)
before porting anything here.

## Project Spec

- Read `docs/sponsor-spec.md` before planning any feature or architecture work.
- The spec is the sponsor's original text. Never edit it.
- Where the spec and team decisions differ, the "Agreed changes from the
  original spec" section in `CLAUDE.md` wins.
- Before finishing a plan, check it against the spec's pipeline: preference
  capture → retrieval/ranking → itinerary generation → visual presentation →
  iteration/refinement. Flag anything that drifts from it.

## Read these, in order

1. `docs/cirrascale-platform.md` — the LLM platform: endpoint, auth, models,
   request/response shape, gotchas. **Source of truth for anything LLM.**
2. `docs/architecture.md` — how the app is wired (request flow, key files).
3. `docs/conventions.md` — code style, server/client rules, git, local dev.
4. `.claude/skills/cirrascale-inference/` — the skill for making model calls.
5. `docs/features.md` — the feature tracker: what we want to build and where it stands.
6. `docs/frontend-architecture.md` — landing + `/planner`: staged/streamed trip generation, Wikipedia place checks, story UI, globe sync.
7. `docs/monorepo-migration.md` — the npm-workspaces + FastAPI monorepo (apps/web, apps/api, packages/contracts, infra).
8. `docs/api-contract.md` — canonical request/response, NDJSON streaming, JSONL ingestion, Qdrant config.
9. `docs/local-development.md` — run web + api + Qdrant locally (mock mode by default).
10. `docs/cirrascale-integration.md` — where Cirrascale is used and how to switch mock → real.
11. `BACKEND-PROGRESS.md` — live checkpoint for the monorepo/backend work.
12. `docs/data-layer.md` — the Python data & trust layer in `backend/` (scraping, sources, rules).
13. `docs/full-rag-integration.md` — the end-to-end data-grounded path: scraped Tokyo
    JSONL → Cirrascale embeddings → Qdrant → RAG → Llama → streamed itinerary, plus
    local setup and the `scripts/demo-full-rag.sh` demo.

## The golden rules

- **One integration point:** all inference goes through `complete()` in
  `src/lib/cirrascale.ts`. Never `fetch` the endpoint elsewhere.
- **Key is server-only:** `CIRRASCALE_API_KEY` never reaches the browser.
- **Prompts live in** `src/lib/planner.ts`, not inline.
- **Keep it basic:** smallest change that works; update the matching doc in the
  same commit.

## Run it

```bash
cp .env.example .env.local   # add CIRRASCALE_API_KEY (free key: aisuite.cirrascale.com)
npm install
npm run dev                  # http://localhost:3000  →  /planner
```

## Map

```
src/app/page.tsx            Landing page (photo hero; prompt → /planner?q=)
src/app/planner/page.tsx    Globe + trip story UI (client) → POST /api/itinerary
src/app/planner/chat/       Legacy chat UI → POST /api/plan
src/app/api/itinerary/      Streams a trip as NDJSON (outline, then each stop)
src/app/api/plan/route.ts   Markdown plan → Cirrascale
src/lib/cirrascale.ts       The inference client (only caller of the endpoint)
src/lib/planner.ts          Prompt construction (all prompts)
src/lib/trip/*              Trip types, generation pipeline, quality checks,
                            Wikipedia places/photos, share links, formatting
src/lib/store/trip.ts       Zustand trip store (streaming state, focus/hover)
src/lib/destinations.ts     Curated landing/sample photos + prompts
src/components/globe/*      3D globe (react-globe.gl)
src/components/trip/*       Composer, chips, overview, stop/activity cards
src/components/landing/*    Landing hero + sample trips
src/components/ui/*         Reused UI primitives (shadcn + magic-ui)
docs/*                      Steering docs (read these)
backend/                    Python data layer (scraping, cleaning, enrichment, JSONL export); see backend/README.md
scraper/                    More sources: OSM, Wikidata coords, DuckDuckGo + Scrapy crawl; see scraper/README.md
```
