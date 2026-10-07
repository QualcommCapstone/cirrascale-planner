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

## Read these, in order

1. `docs/cirrascale-platform.md` — the LLM platform: endpoint, auth, models,
   request/response shape, gotchas. **Source of truth for anything LLM.**
2. `docs/architecture.md` — how the app is wired (request flow, key files).
3. `docs/conventions.md` — code style, server/client rules, git, local dev.
4. `.claude/skills/cirrascale-inference/` — the skill for making model calls.
5. `docs/features.md` — feature specs, one per Jira epic (status lives in Jira).

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
src/app/page.tsx            Landing page
src/app/planner/page.tsx    Chat UI (client) → POST /api/plan
src/app/api/plan/route.ts   Server route → Cirrascale
src/lib/cirrascale.ts       The inference client (only caller of the endpoint)
src/lib/planner.ts          Prompt construction
src/components/ui/*          Reused UI primitives (shadcn + magic-ui)
docs/*                       Steering docs (read these)
```
