"""DuckDuckGo search through the maintained `ddgs` library.

`ddgs` defaults to "auto", which queries several engines (Bing, Google, ...). We pin
`backend="duckduckgo"` so discovery uses DuckDuckGo only, as the team decided, and wait
between queries to keep the volume low. Note: `ddgs` works by calling DuckDuckGo's
public web endpoints, not an official API; keep usage small and switch to an
authorized search API (another `SearchProvider`) if volume grows.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from travel_scraper.discovery.base import DiscoveryError, SearchHit


def _default_client() -> Any:
    from ddgs import DDGS

    return DDGS(timeout=10)


class DuckDuckGoProvider:
    name = "duckduckgo"

    def __init__(
        self,
        *,
        delay_s: float = 3.0,
        region: str = "wt-wt",
        client_factory: Callable[[], Any] = _default_client,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.delay_s = delay_s
        self.region = region
        self._factory = client_factory
        self._client: Any = None
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def search(self, query: str, max_results: int) -> list[SearchHit]:
        if self._last is not None:
            remaining = self._last + self.delay_s - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()
        if self._client is None:
            self._client = self._factory()
        try:
            rows = self._client.text(
                query,
                region=self.region,
                safesearch="moderate",
                max_results=max_results,
                backend="duckduckgo",
            )
        except Exception as exc:  # ddgs: DDGSException, RatelimitException, TimeoutException
            raise DiscoveryError(f"{type(exc).__name__}: {exc}") from exc
        hits: list[SearchHit] = []
        for row in rows or []:
            url = str(row.get("href") or row.get("url") or "")
            if url:
                hits.append(
                    SearchHit(
                        url=url, title=str(row.get("title", "")), snippet=str(row.get("body", ""))
                    )
                )
        return hits
