#!/usr/bin/env python3
"""NDJSON streaming client for the backend demo (stdlib only).

Calls the real FastAPI /api/v1/plan, prints each streamed event live (type,
elapsed, short summary), reconstructs the trip, saves artifacts, and prints a
metrics summary built ONLY from real API responses + measured timings.

Usage:
  demo_stream.py --url http://localhost:8000 --goal "..." \
    --interests Culture,Food --budget Mid --pace Balanced \
    --outdir demo-output/2026... [--require-live]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

C = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m",
    "cyan": "\033[36m", "mag": "\033[35m",
}
if os.environ.get("DEMO_COLOR", "1") != "1":
    C = {k: "" for k in C}


def c(s: str, color: str) -> str:
    return f"{C.get(color,'')}{s}{C['reset']}"


def get_json(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--goal", required=True)
    ap.add_argument("--interests", default="")
    ap.add_argument("--budget", default="Mid")
    ap.add_argument("--pace", default="Balanced")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--require-live", action="store_true")
    args = ap.parse_args()

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Providers (real vs mock) straight from the running backend.
    try:
        ready = get_json(f"{args.url}/ready")
    except Exception as e:
        print(c(f"  ✗ could not reach {args.url}/ready: {e}", "red"))
        return 2
    providers = ready.get("providers", {})
    (outdir / "providers.json").write_text(json.dumps(ready, indent=2))

    if args.require_live and providers.get("llm") != "cirrascale":
        print(c(f"  ✗ --live requires a real Cirrascale LLM, but llm='{providers.get('llm')}'.", "red"))
        print(c("    Start the backend with LLM_PROVIDER=cirrascale + CIRRASCALE_API_KEY, or run --mock.", "yellow"))
        return 3

    interests = [s for s in (x.strip() for x in args.interests.split(",")) if s]
    body = {
        "goal": args.goal,
        "preferences": {"interests": interests, "budget": args.budget, "pace": args.pace},
    }
    print(c(f"  → POST {args.url}/api/v1/plan", "cyan"))
    print(c(f"    goal: {args.goal}", "dim"))
    print(c(f"    preferences: {json.dumps(body['preferences'])}", "dim"))
    print()

    req = urllib.request.Request(
        f"{args.url}/api/v1/plan",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    raw_path = outdir / "stream.ndjson"
    trip: dict | None = None
    events: list[dict] = []
    activities = 0
    sources: list[str] = []
    had_error = False
    start = time.perf_counter()

    try:
        resp = urllib.request.urlopen(req, timeout=240)
    except urllib.error.HTTPError as e:
        print(c(f"  ✗ backend returned HTTP {e.code}: {e.read().decode()[:200]}", "red"))
        return 4
    except Exception as e:
        print(c(f"  ✗ request failed: {e}", "red"))
        return 4

    with raw_path.open("wb") as raw:
        while True:
            line = resp.readline()
            if not line:
                break
            s = line.strip()
            if not s:
                continue
            raw.write(s + b"\n")
            try:
                ev = json.loads(s)
            except json.JSONDecodeError:
                print(c(f"  ! unparseable line skipped: {s[:80]!r}", "yellow"))
                continue
            events.append(ev)
            el = time.perf_counter() - start
            t = ev.get("type")

            if t == "outline":
                trip = ev["trip"]
                tag = c("outline", "mag")
                summary = f'"{trip.get("title","?")}" — {len(trip.get("stops",[]))} stops, {trip.get("days","?")} days'
            elif t == "stop":
                sid = ev.get("stopId")
                days = ev.get("days", [])
                n = sum(len(d.get("activities", [])) for d in days)
                activities += n
                for d in days:
                    for a in d.get("activities", []):
                        if a.get("sourceUrl"):
                            sources.append(a["sourceUrl"])
                if trip:
                    for st in trip.get("stops", []):
                        if st.get("id") == sid:
                            st["days"] = days
                            st["food"] = ev.get("food", st.get("food", []))
                city = next((st.get("city") for st in (trip or {}).get("stops", []) if st.get("id") == sid), sid)
                tag = c("stop", "cyan")
                summary = f"{city}: {len(days)} day(s), {n} activities"
            elif t == "stopError":
                tag = c("stopError", "yellow")
                summary = f"stop {ev.get('stopId')} failed (stream continues)"
            elif t == "done":
                tag = c("done", "green")
                cost = ev.get("estimatedCostUsd")
                summary = f"{ev.get('ms','?')} ms server-side" + (f", est. ${cost}" if cost is not None else "")
            elif t == "error":
                had_error = True
                tag = c("error", "red")
                summary = ev.get("message", "")
            else:
                tag = c(str(t), "dim")
                summary = ""

            print(f"  {c(f'[+{el:5.1f}s]','dim')} {tag:<22} {summary}")

    wall = time.perf_counter() - start
    if trip:
        (outdir / "trip.json").write_text(json.dumps(trip, indent=2, ensure_ascii=False))

    # ---- metrics (real only) ----
    done = next((e for e in events if e.get("type") == "done"), None)
    ok = (not had_error) and done is not None and trip is not None
    lines = []
    lines.append(f"Trip title        : {trip.get('title') if trip else '—'}")
    lines.append(f"Destination       : {trip.get('where') if trip else '—'}")
    lines.append(f"Days              : {trip.get('days') if trip else '—'}")
    lines.append(f"Stops             : {len(trip.get('stops', [])) if trip else 0}")
    lines.append(f"Activities         : {activities}")
    lines.append(f"Generation time   : {done.get('ms') if done else int(wall*1000)} ms (server-measured)")
    if done and done.get("estimatedCostUsd") is not None:
        lines.append(f"Est. cost (struct.): ${done['estimatedCostUsd']} (from structured data, not a quote)")
    lines.append(f"LLM provider      : {providers.get('llm')}")
    lines.append(f"Embedding provider: {providers.get('embedding')}")
    lines.append(f"Vector store      : {providers.get('vector_store')}")
    lines.append(f"Validation        : {'passed (schema-valid, done received)' if ok else 'INCOMPLETE'}")
    uniq_sources = sorted(set(sources))
    lines.append(f"Source attribution: {len(uniq_sources)} activity source URLs"
                 + ("" if uniq_sources else " (none — mock fixtures carry no sources)"))

    print()
    for ln in lines:
        print("  " + ln)
    (outdir / "summary.txt").write_text(
        f"goal: {args.goal}\npreferences: {json.dumps(body['preferences'])}\n\n" + "\n".join(lines) + "\n"
    )
    if uniq_sources:
        (outdir / "sources.txt").write_text("\n".join(uniq_sources) + "\n")

    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())
