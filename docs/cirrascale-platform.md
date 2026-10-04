# Cirrascale / Qualcomm AI Inference Suite — Platform Reference

> Agent steering doc. This is the single source of truth for how we talk to the
> LLM platform. If the API behaves differently from what's written here, fix
> this file in the same change.

## What it is

The **Qualcomm AI Inference Suite** is a hosted LLM inference service running on
**Qualcomm Cloud AI 100 Ultra** accelerators, offered as a free-to-try cloud by
**Cirrascale**. We use it as the only LLM backend for this project.

- Console / sign-up: https://aisuite.cirrascale.com
- It is a **text-completions** API (`prompt` string in, `text` out). It is **not**
  an OpenAI chat/messages API — there is no `messages` array and no `role` field.

## Endpoint

```
POST https://aisuite.cirrascale.com/apis/v2/completions
```

Headers:

| Header          | Value                       |
| --------------- | --------------------------- |
| `Content-Type`  | `application/json`          |
| `Authorization` | `Bearer <CIRRASCALE_API_KEY>` |

Request body:

| Field        | Type    | Notes                                              |
| ------------ | ------- | -------------------------------------------------- |
| `prompt`     | string  | The full prompt. Build chat/system framing by hand.|
| `model`      | string  | e.g. `Llama-3.1-8B` (see Models).                  |
| `stream`     | boolean | `false` for a single JSON response.                |
| `max_tokens` | number  | Upper bound on generated tokens.                   |

Response (non-streaming):

```json
{ "choices": [{ "text": "...generated text..." }] }
```

Read the output from `data.choices[0].text`.

## Minimal example

```bash
curl -s https://aisuite.cirrascale.com/apis/v2/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $CIRRASCALE_API_KEY" \
  -d '{"prompt":"List three uses for a paperclip.","model":"Llama-3.1-8B","stream":false,"max_tokens":128}'
```

```js
const res = await fetch("https://aisuite.cirrascale.com/apis/v2/completions", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${process.env.CIRRASCALE_API_KEY}`,
  },
  body: JSON.stringify({
    prompt: "List three uses for a paperclip.",
    model: "Llama-3.1-8B",
    stream: false,
    max_tokens: 128,
  }),
});
const data = await res.json();
console.log(data.choices[0].text);
```

## Models

Starter set on the free-to-try tier (confirm the live list in the console):

- `Llama-3.1-8B` — default. Fast, cheap, good for planning.
- `Llama-3.1-70B` — stronger reasoning, slower.
- `Qwen2.5-7B-Instruct` — alternative instruct model.

Qualcomm says the suite ships "a starter set of popular open-source GenAI models"
and will add user-provided models later, so treat the list as changeable. The
canonical list in code lives in `KNOWN_MODELS` (`src/lib/cirrascale.ts` in the
planner, `lib/cirrascale.mjs` in the sandbox).

## Auth / keys

- Get a key from https://aisuite.cirrascale.com (free to try).
- Store it in `CIRRASCALE_API_KEY`. **Never** commit it or expose it to the
  browser — all calls go through server code (Next.js route handlers / Node
  scripts). See `.env.example`.

## Prompting notes (completions, not chat)

Because there's a single `prompt` string, we fake chat framing: concatenate a
system instruction, the user content, and guardrails into one string. See
`buildPlannerPrompt()` in `src/lib/planner.ts`. Keep the system instruction
first and repeat the key output constraint at the end ("return ONLY ...").

## Gotchas

- Don't send `messages` — it's ignored; the model only sees `prompt`.
- Trim the response; models often add leading whitespace.
- Larger models can be slow; set `cache: "no-store"` and expect multi-second latency.
- On non-2xx, read the response body text for the real error.

## Sources

- https://www.cirrascale.com/blogs/using-the-qualcomm-ai-inference-suite-directly-from-a-web-page
- https://www.qualcomm.com/developer/blog/2025/08/ai-inference-with-google-colab
- https://www.cirrascale.com/ai-innovation-cloud/qualcomm-cloud-ai
