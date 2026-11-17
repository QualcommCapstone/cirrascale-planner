"""Environment-based configuration (pydantic-settings).

Every endpoint, key, model id, timeout and provider selection is configurable so
mock mode and production differ only by env, never by code. Secrets live here and
never leave the server.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    # Comma-separated in env, e.g. "http://localhost:3000,https://app.example.com"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- provider selection (mock mode by default) ---
    embedding_provider: EmbeddingProvider = "mock"
    vector_store_provider: VectorStoreProvider = "memory"
    llm_provider: LLMProvider = "mock"

    # --- Cirrascale (LLM; embedding endpoint TBD) ---
    cirrascale_api_key: str | None = None
    cirrascale_base_url: str = "https://aisuite.cirrascale.com/apis/v2"
    cirrascale_model: str = "Llama-3.1-8B"
    # The embedding model/endpoint/dimension are not confirmed yet.
    cirrascale_embedding_model: str | None = None
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
        # Accept a comma-separated string from env as well as a real list/JSON.
        if isinstance(v, str) and not v.strip().startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def has_cirrascale_key(self) -> bool:
        return bool(self.cirrascale_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
