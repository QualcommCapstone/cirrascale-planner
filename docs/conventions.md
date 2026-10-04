# Conventions — cirrascale-planner

> Agent steering doc. Follow these so handoffs stay clean.

## Code

- **TypeScript, strict.** No `any` unless unavoidable and commented.
- **Imports** use the `@/*` alias (maps to `src/*`).
- **Server vs client:** files calling Cirrascale or reading `process.env` must be
  server (route handlers, `src/lib/*` used only by the server). Client components
  start with `"use client"`.
- **Styling:** Tailwind utility classes + the design tokens in `globals.css`
  (`bg-background`, `text-foreground`, etc.). Reuse `src/components/ui/*` before
  writing new components. Use `cn()` from `@/lib/utils` to merge classes.
- **Keep it basic.** This is a starter. Prefer the smallest change that works over
  new abstractions, dependencies, or infrastructure.

## LLM usage

- Only `src/lib/cirrascale.ts` may call the inference endpoint.
- Prompt text lives in `src/lib/planner.ts`, not inline in components or routes.
- Never log or return the API key.

## Docs / steering (this project's workflow)

- Markdown files in `docs/` and `AGENTS.md` are the handoff contract. When you
  change behavior, update the matching doc in the **same** commit.
- `AGENTS.md` is the entry point; `CLAUDE.md` just points to it.
- If reality and a doc disagree, the code wins — then fix the doc.

## Git

- Small, focused commits with clear messages.
- Don't commit `.env*` (only `.env.example`).
- Branch off `main` for changes.

## Local dev

```bash
cp .env.example .env.local   # add CIRRASCALE_API_KEY
npm install
npm run dev                  # http://localhost:3000
```
