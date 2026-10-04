---
name: cirrascale-inference
description: >-
  Call the Qualcomm AI Inference Suite (hosted by Cirrascale) — the LLM backend
  for this project. Use whenever you need to run an LLM completion, add or change
  a model call, debug an inference request/response, pick a model, or build a
  prompt. Covers the completions endpoint, auth, request/response shape, model
  list, and the project's server-only key rule.
---

# Cirrascale / Qualcomm AI Inference Suite

The only LLM backend for this project. It is a **text-completions** API (single
`prompt` string → `choices[0].text`), **not** an OpenAI chat API.

## When to use this skill

- Adding or editing any LLM call.
- Debugging a failing inference request (auth, 4xx/5xx, bad response shape).
- Choosing a model or changing prompt-building logic.
- Writing a new script/route that needs the model.

## The contract

```
POST https://aisuite.cirrascale.com/apis/v2/completions
Headers: Content-Type: application/json
         Authorization: Bearer <CIRRASCALE_API_KEY>
Body:    { "prompt": "...", "model": "Llama-3.1-8B", "stream": false, "max_tokens": 1024 }
Reply:   { "choices": [{ "text": "..." }] }
```

Default model `Llama-3.1-8B`. Also available: `Llama-3.1-70B`,
`Qwen2.5-7B-Instruct`. Confirm the live list at https://aisuite.cirrascale.com.

## Rules for this repo

1. **Never call the endpoint directly.** Use the shared client:
   - Planner app: `complete()` in `src/lib/cirrascale.ts`.
   - Sandbox: `complete()` in `lib/cirrascale.mjs`.
2. **Key is server-only.** Read `CIRRASCALE_API_KEY` from env, never ship it to the
   browser, never log it. Copy `.env.example` → `.env.local` (planner) or `.env`
   (sandbox).
3. **Build prompts, not messages.** There is no `messages` array. Concatenate
   system instruction + user content + guardrails into one `prompt` string
   (see `buildPlannerPrompt` in `src/lib/planner.ts`).
4. **Handle errors.** On non-2xx, read the response body for the real message.
   Trim the returned text.

## Quick test

```bash
curl -s https://aisuite.cirrascale.com/apis/v2/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CIRRASCALE_API_KEY" \
  -d '{"prompt":"Say hello.","model":"Llama-3.1-8B","stream":false,"max_tokens":16}'
```

## Full reference

See `docs/cirrascale-platform.md` for the complete platform doc, gotchas, and
sources.
