# Architecture — cirrascale-planner

> Agent steering doc. Read this before changing how the app is wired.

## One-liner

A Next.js 14 (App Router) app that turns a one-sentence prompt into a visual
trip: real places with photos, a day-by-day plan and a route on a globe. The
browser never talks to Cirrascale directly — it posts to our own
`/api/itinerary` route, which calls the Qualcomm AI Inference Suite server-side
and checks places against Wikipedia.

## Request flow

```
Browser (/planner)
  │  POST /api/itinerary  { goal, preferences }      (validated with zod)
  ▼
Route handler  src/app/api/itinerary/route.ts  → NDJSON stream
  │  generateTrip()                     → src/lib/trip/generate.ts
  │    buildOutlinePrompt / buildDaysPrompt   → src/lib/planner.ts
  │    complete(prompt, { maxTokens })        → src/lib/cirrascale.ts
  │    parse + quality gate + retry           → src/lib/trip/normalize.ts, quality.ts
  │    verify places + photos                 → src/lib/trip/places.ts (Wikipedia API)
  ▼
{"type":"outline"} → {"type":"stop"} × N → {"type":"done","ms"}
```

Details (stages, content rules, Wikipedia matching, UI): `docs/frontend-architecture.md`.
The legacy markdown chat (`/planner/chat` → `/api/plan`) still works unchanged.

## Key files

| File                              | Responsibility                                         |
| --------------------------------- | ------------------------------------------------------ |
| `src/lib/cirrascale.ts`           | The only place that calls the inference endpoint.      |
| `src/lib/planner.ts`              | All prompts (markdown plan, trip outline, stop days).  |
| `src/lib/trip/generate.ts`        | Staged trip generation + streaming events.             |
| `src/lib/trip/places.ts`          | Wikipedia place verification and photos (no API key).  |
| `src/app/api/itinerary/route.ts`  | HTTP boundary: validates input, streams NDJSON.        |
| `src/app/api/plan/route.ts`       | Legacy: returns a Markdown `{ plan }`.                  |
| `src/app/planner/page.tsx`        | Globe + trip story UI (client).                        |
| `src/app/page.tsx`                | Landing page.                                          |
| `src/components/ui/*`             | shadcn/ui + magic-ui primitives (reused from ORBIT).   |

## Design rules

1. **Server-only secrets.** `CIRRASCALE_API_KEY` is read only inside
   `src/lib/cirrascale.ts` (server). Never import that module into a client
   component.
2. **One integration point.** All Cirrascale calls go through `complete()`. Don't
   `fetch` the endpoint from anywhere else.
3. **Prompt logic is isolated** in `src/lib/planner.ts` so it can be tuned
   without touching transport or UI.
4. **UI is reused, not rebuilt.** Primitives come from the ORBIT project
   (shadcn new-york style + Tailwind tokens in `globals.css`).

## Extending (ideas, keep it basic)

- **Model picker:** `GET /api/plan` returns `KNOWN_MODELS`; add a `<select>` and
  pass `model` in the POST body.
- **Grounding / scraper:** `buildPlannerPrompt(goal, context)` already accepts a
  `context` string. Fetch a URL server-side, extract text, pass it in. The
  `cirrascale-sandbox` repo has a working `scrape-and-plan` script to copy from.
- **Streaming:** the endpoint supports `stream: true`; would require switching
  the route to a streamed response and the client to read chunks.

## Stack

Next.js 14.2 · React 18 · TypeScript · Tailwind + tailwindcss-animate +
typography · shadcn/ui · framer-motion (flip text) · react-markdown ·
next-themes. No auth, no database — intentionally minimal.
