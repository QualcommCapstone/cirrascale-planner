"""Test hardening: the suite must never call real Cirrascale or Qdrant.

A developer running a live backend will have apps/api/.env set to
LLM_PROVIDER=cirrascale etc. Settings reads that .env, and app.main captures
settings at import — so without this, importing the app for tests would wire the
real providers and tests would hit the network. Forcing mock providers in the
process environment here (before any app import) keeps the suite hermetic and
fast everywhere. CI already runs in mock mode, so this is a no-op there.
"""

import os

# Opt-in live tests (RUN_LIVE_RAG=1) deliberately use real Cirrascale + Qdrant, so
# don't strip the environment out from under them. Everything else stays hermetic.
if not os.getenv("RUN_LIVE_RAG"):
    os.environ["EMBEDDING_PROVIDER"] = "mock"
    os.environ["VECTOR_STORE_PROVIDER"] = "memory"
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ.pop("CIRRASCALE_API_KEY", None)
