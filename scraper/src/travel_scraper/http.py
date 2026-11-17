"""A polite client for official JSON APIs (Overpass, Wikidata).

APIs follow their own usage policies rather than robots.txt (robots.txt is for
crawlers; Wikimedia's even disallows `/w/`, where its API lives, for crawlers):

- an honest User-Agent on every request
- one request at a time per host, with a minimum delay between them
- retries with growing waits on network errors, timeouts, 429 and 5xx, honoring `Retry-After`
- **HTTP 200 that is really an error counts as a failure.** A `check` callback inspects
  each JSON body and raises `RetryableResponse` (Overpass partial data, Wikidata `maxlag`).
  If retries run out, the call raises `ApiFailed` and the partial data is discarded.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

log = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
# Never sleep longer than this on one retry, whatever the server asks.
MAX_RETRY_AFTER_S = 120.0

Check = Callable[[Any], None]


class RetryableResponse(Exception):
    """A 200 response whose body says the request failed. Retried like a 5xx."""

    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class ApiFailed(Exception):
    """The API call failed, even after retrying."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url}: {reason}")
        self.url = url
        self.reason = reason


class ApiClient:
    def __init__(
        self,
        *,
        user_agent: str,
        min_delay_s: float | Mapping[str, float] = 1.0,
        max_attempts: int = 4,
        backoff_s: float = 2.0,
        timeout_s: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.user_agent = user_agent
        self._delays = min_delay_s
        self.max_attempts = max(1, max_attempts)
        self.backoff_s = backoff_s
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=timeout_s,
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ApiClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def delay_for(self, host: str) -> float:
        if isinstance(self._delays, Mapping):
            return float(self._delays.get(host, self._delays.get("*", 1.0)))
        return float(self._delays)

    def get_json(
        self, url: str, params: Mapping[str, str] | None = None, check: Check | None = None
    ) -> Any:
        return self._request("GET", url, params=params, data=None, check=check)

    def post_json(self, url: str, data: Mapping[str, str], check: Check | None = None) -> Any:
        return self._request("POST", url, params=None, data=data, check=check)

    # ---- internals --------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None,
        data: Mapping[str, str] | None,
        check: Check | None,
    ) -> Any:
        last_reason = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            self._wait_turn(url)
            retry_after: float | None = None
            try:
                response = self._client.request(method, url, params=params, data=data)
            except httpx.HTTPError as exc:
                last_reason = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code == 200:
                    try:
                        body = response.json()
                        if check is not None:
                            check(body)
                        return body
                    except RetryableResponse as exc:
                        last_reason = exc.reason
                        retry_after = exc.retry_after
                    except ValueError as exc:  # not JSON
                        last_reason = f"invalid JSON: {exc}"
                else:
                    last_reason = f"HTTP {response.status_code}"
                    if response.status_code not in RETRY_STATUSES:
                        raise ApiFailed(url, last_reason)
                    retry_after = _retry_after(response)

            if attempt < self.max_attempts:
                wait = (
                    min(retry_after, MAX_RETRY_AFTER_S)
                    if retry_after is not None
                    else self.backoff_s * 2 ** (attempt - 1)
                )
                log.warning(
                    "Attempt %d for %s failed (%s); retrying in %.1fs",
                    attempt,
                    url,
                    last_reason,
                    wait,
                )
                self._sleep(wait)
        raise ApiFailed(url, f"gave up after {self.max_attempts} attempts ({last_reason})")

    def _wait_turn(self, url: str) -> None:
        host = urlsplit(url).netloc.lower()
        last = self._last.get(host)
        if last is not None:
            remaining = last + self.delay_for(host) - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last[host] = self._clock()


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return min(MAX_RETRY_AFTER_S, max(0.0, float(value)))
    except ValueError:
        return None
