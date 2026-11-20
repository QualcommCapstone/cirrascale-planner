# Cirrascale Integration

Where the Qualcomm AI Inference Suite (hosted by Cirrascale) is used, and how keys
flow. Full platform reference: `docs/cirrascale-platform.md`.

## Integration points

| Where | File | Use |
| ----- | ---- | --- |
| Web (current) | `apps/web/src/lib/cirrascale.ts` | `complete()` — the in-Next trip pipeline + legacy `/api/plan`. |
| Backend LLM | `apps/api/app/providers/llm.py` | `CirrascaleLLMProvider` — reuses the same completions config (Bearer key, `{prompt, model, stream, max_tokens}` → `choices[0].text`) with pooling, timeout, bounded retries. |
| Backend embedding | `apps/api/app/providers/embedding.py` | `CirrascaleEmbeddingProvider` — **implemented**. OpenAI-compatible `POST /embeddings`; `BAAI/bge-base-en-v1.5` (768-dim, default) or `BAAI/bge-large-en-v1.5` (1024-dim). Batched, pooled, retried; dim fixed by the model. |

All three are selected by config and are server-only.

## Keys & config

- `CIRRASCALE_API_KEY` is read only on the server (web route handlers / backend
  providers) and never shipped to the browser.
- Model default `Llama-3.1-8B`. **`Llama-3.1-70B` returns HTTP 429** ("model not
  configured") on the free tier — do not default to it.
- Backend env: `LLM_PROVIDER=cirrascale` to use the real model; `EMBEDDING_PROVIDER`
  stays `mock` until the embedding service ships.

## Switching from mock to real

1. **LLM**: set `LLM_PROVIDER=cirrascale` + `CIRRASCALE_API_KEY`. Done — the RAG
   pipeline is unchanged.
2. **Embedding**: set `EMBEDDING_PROVIDER=cirrascale` (+ `CIRRASCALE_API_KEY`).
   Default model `BAAI/bge-base-en-v1.5` (768-dim); `BAAI/bge-large-en-v1.5` is
   1024-dim. The dimension is fixed by the model (no `VECTOR_DIM` needed for real
   embeddings). Re-ingest so the Qdrant collection holds one model/space (payloads
   carry `model_version` to enforce this). `EMBEDDING_QUERY_INSTRUCTION` is off by
   default — the hosted BGE scored worse with the usual BGE query instruction.
3. **Vector store**: `VECTOR_STORE_PROVIDER=qdrant` + `QDRANT_URL`, then ingest
   JSONL (`docs/api-contract.md`).

## Known limitations

- Embedding **retrieval quality** on `bge-base` is modest on short/sparse text
  (it can rank a generic food blurb above a nightlife one). Expect it to improve
  with real scraped descriptions and/or `bge-large`; worth an eval pass. The
  converter itself is verified correct (batched == individual embeddings; dim
  matches the store).
- 8B output is modest; the backend grounds activities in retrieved places and
  flags unverified ones rather than trusting the model's claims.
- Unit tests never call Cirrascale or Qdrant (mock/in-memory only).

## Future production

A real embedding model + a populated Qdrant (from the scraper's JSONL via
`app.ingest`) turns mock RAG into real retrieval with only env changes. Add auth,
rate limiting, and observability at the edge before exposing `/api/v1/*` publicly.
