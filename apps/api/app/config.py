"""Environment-based configuration (pydantic-settings).

Every endpoint, key, model id, timeout and provider selection is configurable so
mock mode and production differ only by env, never by code. Secrets live here and
never leave the server.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

EmbeddingProvider = Literal["mock", "cirrascale"]
VectorStoreProvider = Literal["memory", "qdrant"]
LLMProvider = Literal["mock", "cirrascale"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- app ---
    app_env: str = "development"
    log_level: str = "INFO"
    # Comma-separated in env, e.g. "http://localhost:3000,https://app.example.com".
    # NoDecode stops pydantic-settings from JSON-decoding the env value at the
    # source (which rejects a plain string); the validator below splits it.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- provider selection (mock mode by default) ---
    embedding_provider: EmbeddingProvider = "mock"
    vector_store_provider: VectorStoreProvider = "memory"
    llm_provider: LLMProvider = "mock"

    # --- Cirrascale (LLM; embedding endpoint TBD) ---
    cirrascale_api_key: str | None = None
    cirrascale_base_url: str = "https://aisuite.cirrascale.com/apis/v2"
    cirrascale_model: str = "Llama-3.1-8B"
    # Cirrascale embedding model (OpenAI-compatible /embeddings). Options:
    #   BAAI/bge-base-en-v1.5  (768-dim, default)   BAAI/bge-large-en-v1.5 (1024-dim)
    cirrascale_embedding_model: str | None = None
    embedding_batch_size: int = 64
    # Optional instruction prepended to QUERIES only. BGE docs suggest one, but the
    # Cirrascale-hosted BGE scored worse with it, so default off. See docs.
    embedding_query_instruction: str = ""
    request_timeout_seconds: float = 60.0

    # --- vector store ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "places"
    # Vector dimension is tied to the embedding model; the mock uses this too.
    vector_dim: int = 384

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        # Env value arrives as a raw string (NoDecode). Accept both a JSON array
        # and a comma-separated list.
        if isinstance(v, str):
            s = v.strip()
            if s.startswith("["):
                import json

                return json.loads(s)
            return [o.strip() for o in s.split(",") if o.strip()]
        return v

    @property
    def has_cirrascale_key(self) -> bool:
        return bool(self.cirrascale_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
