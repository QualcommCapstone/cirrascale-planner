# cirrascale-planner

Turn any prompt into a structured, step-by-step **plan** — powered by the
**Qualcomm AI Inference Suite** (Qualcomm Cloud AI 100 Ultra) hosted by
**Cirrascale**.

This is the **main platform**. For experiments, see the sibling
[`cirrascale-sandbox`](https://github.com/QualcommCapstone/cirrascale-sandbox).

## Stack

Next.js 14 (App Router) · TypeScript · Tailwind + shadcn/ui · react-markdown.
UI primitives reused from the ORBIT project. No auth, no database — intentionally
minimal.

## Quick start

```bash
cp .env.example .env.local        # add your CIRRASCALE_API_KEY
npm install
npm run dev                       # http://localhost:3000
```

Open `/planner`, type a goal, get a plan.

Get a free-to-try key at **https://aisuite.cirrascale.com**.

## How it works

The browser posts a goal to `/api/plan`. That server route builds a planner
prompt and calls the Cirrascale completions endpoint (keeping the API key
server-side), then returns Markdown that the chat UI renders.

```
/planner (client) → POST /api/plan → src/lib/cirrascale.ts → Cirrascale → { plan }
```

## For agents / contributors

Start with **[AGENTS.md](./AGENTS.md)**. Steering docs live in [`docs/`](./docs),
and `.claude/skills/cirrascale-inference/` documents how to call the model.

## Environment

| Variable              | Default                                      | Notes               |
| --------------------- | -------------------------------------------- | ------------------- |
| `CIRRASCALE_API_KEY`  | —                                            | Required.           |
| `CIRRASCALE_BASE_URL` | `https://aisuite.cirrascale.com/apis/v2`     | Optional override.  |
| `CIRRASCALE_MODEL`    | `Llama-3.1-8B`                               | Default model.      |
