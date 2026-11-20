"""In-process pipeline monitor: a tiny event bus the RAG flow writes to and the
/monitor dashboard reads (snapshot + Server-Sent Events).

It is best-effort and never affects request handling: recording is non-blocking and
swallows a full subscriber queue rather than raising. Everything lives in memory for
the life of the process — this is live observability for a demo, not durable metrics.
"""

from __future__ import annotations

import asyncio
import collections
import time
from typing import Any

_MAX_EVENTS = 250
_events: collections.deque[dict] = collections.deque(maxlen=_MAX_EVENTS)
_counters: collections.Counter[str] = collections.Counter()
_subscribers: set[asyncio.Queue[dict]] = set()
_seq = 0
_started = time.time()

# Human-facing stage order for the dashboard pipeline.
STAGES = ("request", "embed", "retrieve", "llm", "done")


def record(stage: str, message: str, **data: Any) -> None:
    """Append one pipeline event and fan it out to live subscribers."""
    global _seq
    _seq += 1
    evt = {
        "seq": _seq,
        "ts": round(time.time(), 3),
        "stage": stage,
        "message": message,
        "data": data,
    }
    _events.append(evt)
    _counters[stage] += 1
    for q in list(_subscribers):
        try:
            q.put_nowait(evt)
        except asyncio.QueueFull:
            pass


def snapshot() -> dict:
    """Current counters + the recent event ring (newest last)."""
    return {
        "uptime_s": round(time.time() - _started, 1),
        "counters": dict(_counters),
        "events": list(_events),
    }


def add_subscriber() -> asyncio.Queue[dict]:
    q: asyncio.Queue[dict] = asyncio.Queue(maxsize=200)
    _subscribers.add(q)
    return q


def remove_subscriber(q: asyncio.Queue[dict]) -> None:
    _subscribers.discard(q)
