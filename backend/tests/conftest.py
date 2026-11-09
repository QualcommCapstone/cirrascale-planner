"""Shared test helpers: fake HTTP responses and a fake clock, so tests never touch the network."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from scrapling.parser import Selector

from app.scraping.fetch import FetcherKind, PoliteFetcher

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse:
    """Looks like a Scrapling Response: status, body, headers, and .css()."""

    def __init__(self, status: int = 200, body: str = "", headers: dict[str, str] | None = None):
        self.status = status
        self.body = body.encode("utf-8")
        self.headers = headers or {}
        self._selector = Selector(body or "<html></html>", url="")

    def css(self, selector: str) -> Any:
        return self._selector.css(selector)


Route = FakeResponse | Exception | list[FakeResponse | Exception]


class FakeHttp:
    """Stands in for `scrapling_get`. Maps URL -> response (or a list played in order)."""

    def __init__(self, routes: dict[str, Route]):
        self.routes = {url: list(r) if isinstance(r, list) else [r] for url, r in routes.items()}
        self.calls: list[tuple[str, FetcherKind, str]] = []

    def __call__(self, url: str, kind: FetcherKind, user_agent: str, timeout_s: float) -> Any:
        self.calls.append((url, kind, user_agent))
        queue = self.routes.get(url)
        if not queue:
            return FakeResponse(404)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    def urls(self) -> list[str]:
        return [url for url, _, _ in self.calls]


class FakeClock:
    """A clock that only moves when someone 'sleeps'. Records every sleep."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_fetcher(clock: FakeClock) -> Callable[..., PoliteFetcher]:
    def build(http: FakeHttp, **kwargs: Any) -> PoliteFetcher:
        kwargs.setdefault("min_delay_s", 3.0)
        return PoliteFetcher(http_get=http, sleep=clock.sleep, clock=clock.time, **kwargs)

    return build


def fixture_html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")
