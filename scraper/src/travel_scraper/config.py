"""Settings, from environment variables or `scraper/.env` (copy `.env.example`)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# scraper/src/travel_scraper/config.py -> repo root is three levels above `src`.
REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_USER_AGENT = (
    "AI100TravelPlanner-scraper/0.1 "
    "(ASU capstone student project; https://github.com/QualcommCapstone/cirrascale-planner)"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SCRAPER_", extra="ignore")

    # Sent with every request. Wikimedia asks for contact details: add a team email.
    user_agent: str = DEFAULT_USER_AGENT

    # Minimum seconds between two requests to the same host.
    wikidata_delay_s: float = 1.0
    overpass_delay_s: float = 5.0
    search_delay_s: float = 3.0
    crawl_delay_s: float = 3.0

    overpass_url: str = "https://overpass-api.de/api/interpreter"
    wikidata_url: str = "https://www.wikidata.org/w/api.php"

    # Where Aayush's backend/ lives; raw files go to <backend_dir>/data/raw.
    backend_dir: Path = REPO_ROOT / "backend"
    # Discovery output.
    data_dir: Path = Path("data")

    @property
    def raw_dir(self) -> Path:
        return self.backend_dir / "data" / "raw"


@lru_cache
def get_settings() -> Settings:
    return Settings()
