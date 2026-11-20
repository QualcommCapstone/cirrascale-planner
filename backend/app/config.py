"""Settings, read from environment variables or from `backend/.env`.

Copy `.env.example` to `.env` to change them. `.env` is gitignored.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.scraping.fetch import DEFAULT_USER_AGENT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Matches backend/docker-compose.yml. Use `postgresql+psycopg:///planner` for a
    # Postgres already installed on your Mac, or `sqlite:///data/planner.db` for no server.
    database_url: str = "postgresql+psycopg://planner:planner@localhost:5432/planner"

    # Scraper politeness (see docs/data-layer.md).
    scraper_user_agent: str = DEFAULT_USER_AGENT
    scraper_min_delay_s: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
