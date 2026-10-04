# Architecture — cirrascale-planner

> Agent steering doc. Read this before changing how the app is wired.

## One-liner

A Next.js 14 (App Router) app that turns a user's prompt into a structured
Markdown plan. The browser never talks to Cirrascale directly — it posts to our
own `/api/plan` route, which calls the Qualcomm AI Inference Suite server-side.

## Request flow

```
Browser (/planner page)
  │  POST /api/plan  { goal }
  ▼
Route handler  src/app/api/plan/route.ts
  │  buildPlannerPrompt(goal)        → src/lib/planner.ts
  │  complete(prompt, { model })     → src/lib/cirrascale.ts
  ▼
POST https://aisuite.cirrascale.com/apis/v2/completions   (Bearer key)
  ▼
{ choices: [{ text }] }  →  { plan }  →  rendered as Markdown
```

## Key files

| File                          | Responsibility                                        |
| ----------------------------- | ----------------------------------------------------- |
| `src/lib/cirrascale.ts`       | The only place that calls the inference endpoint.     |
| `src/lib/planner.ts`          | Builds the planner prompt (system + goal + guardrails).|
| `src/app/api/plan/route.ts`   | HTTP boundary: validates input, returns `{ plan }`.   |
| `src/app/planner/page.tsx`    | Chat UI (client). Posts to `/api/plan`.               |
| `src/app/page.tsx`            | Landing page.                                          |
| `src/components/ui/*`         | shadcn/ui + magic-ui primitives (reused from ORBIT).  |

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
