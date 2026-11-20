"""ApiClient: delays, retries, Retry-After, and 200-with-error handling."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from tests.conftest import FakeClock
from travel_scraper.http import ApiClient, ApiFailed, RetryableResponse

URL = "https://api.example.org/q"


def client_for(
    responses: list[httpx.Response | Exception], clock: FakeClock, **kw: Any
) -> tuple[ApiClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    client = ApiClient(
        user_agent="test-agent/1.0",
        transport=httpx.MockTransport(handler),
        sleep=clock.sleep,
        clock=clock.time,
        **kw,
    )
    return client, seen


def test_returns_json_and_sends_user_agent(clock: FakeClock) -> None:
    client, seen = client_for([httpx.Response(200, json={"ok": 1})], clock)
    assert client.get_json(URL, params={"a": "b"}) == {"ok": 1}
    assert seen[0].headers["User-Agent"] == "test-agent/1.0"
    assert seen[0].url.params["a"] == "b"


def test_waits_between_requests_to_the_same_host(clock: FakeClock) -> None:
    client, _ = client_for([httpx.Response(200, json={})], clock, min_delay_s=5.0)
    client.get_json(URL)
    client.get_json(URL)
    assert clock.sleeps == [5.0]


def test_per_host_delays(clock: FakeClock) -> None:
    client, _ = client_for(
        [httpx.Response(200, json={})], clock, min_delay_s={"api.example.org": 2.0, "*": 9.0}
    )
    assert client.delay_for("api.example.org") == 2.0
    assert client.delay_for("other.org") == 9.0


def test_retries_5xx_then_succeeds_with_growing_waits(clock: FakeClock) -> None:
    client, seen = client_for(
        [httpx.Response(503), httpx.Response(502), httpx.Response(200, json={"ok": 1})],
        clock,
        min_delay_s=0,
        backoff_s=2.0,
    )
    assert client.get_json(URL) == {"ok": 1}
    assert len(seen) == 3
    assert clock.sleeps == [2.0, 4.0]


def test_honors_retry_after(clock: FakeClock) -> None:
    client, _ = client_for(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={})],
        clock,
        min_delay_s=0,
    )
    client.get_json(URL)
    assert clock.sleeps == [7.0]


def test_404_fails_at_once(clock: FakeClock) -> None:
    client, seen = client_for([httpx.Response(404)], clock, min_delay_s=0)
    with pytest.raises(ApiFailed, match="HTTP 404"):
        client.get_json(URL)
    assert len(seen) == 1


def test_network_errors_are_retried_then_give_up(clock: FakeClock) -> None:
    client, seen = client_for([httpx.ConnectError("boom")], clock, min_delay_s=0, max_attempts=3)
    with pytest.raises(ApiFailed, match="gave up after 3 attempts"):
        client.get_json(URL)
    assert len(seen) == 3


def test_200_that_is_an_error_is_retried(clock: FakeClock) -> None:
    calls = {"n": 0}

    def check(body: Any) -> None:
        calls["n"] += 1
        if body.get("partial"):
            raise RetryableResponse("partial", retry_after=1.5)

    client, _ = client_for(
        [httpx.Response(200, json={"partial": True}), httpx.Response(200, json={"partial": False})],
        clock,
        min_delay_s=0,
    )
    assert client.post_json(URL, {"data": "q"}, check=check) == {"partial": False}
    assert calls["n"] == 2
    assert clock.sleeps == [1.5]


def test_partial_data_is_never_returned_when_retries_run_out(clock: FakeClock) -> None:
    def always_partial(_: Any) -> None:
        raise RetryableResponse("Overpass partial result")

    client, _ = client_for(
        [httpx.Response(200, json={"elements": [1, 2]})], clock, min_delay_s=0, max_attempts=2
    )
    with pytest.raises(ApiFailed, match="partial"):
        client.get_json(URL, check=always_partial)


def test_invalid_json_is_retried(clock: FakeClock) -> None:
    client, _ = client_for(
        [httpx.Response(200, text="<html>busy</html>"), httpx.Response(200, json={"ok": 1})],
        clock,
        min_delay_s=0,
    )
    assert client.get_json(URL) == {"ok": 1}


def test_context_manager_closes(clock: FakeClock) -> None:
    client, _ = client_for([httpx.Response(200, json={})], clock)
    with client as c:
        assert c is client
