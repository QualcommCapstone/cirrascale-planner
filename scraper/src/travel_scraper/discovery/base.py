"""The search-provider interface. Swap DuckDuckGo for another provider (an authorized
search API, say) by implementing `SearchProvider`; nothing else changes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""


class DiscoveryError(Exception):
    """A search failed (rate limit, timeout, provider error). The query is skipped."""


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        """Return hits for one query, or raise `DiscoveryError`."""
        ...
