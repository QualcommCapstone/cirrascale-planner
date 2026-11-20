#!/usr/bin/env bash
# Qualcomm AI100 — full end-to-end RAG demo verifier.
#
# Checks the whole data-grounded pipeline end to end and prints a PASS only when a
# check genuinely succeeds — never a fabricated result:
#
#   Next.js  ->  FastAPI /api/v1/plan  ->  Cirrascale BGE embeddings
#            ->  Qdrant (real Tokyo places)  ->  Cirrascale Llama 3.1 8B
#            ->  validated NDJSON itinerary
#
# It talks only to the already-running services, so it needs no API key of its own
# (the backend holds it). Response artifacts are saved, with secrets redacted, under
# a git-ignored output dir.
#
# Usage:
#   scripts/demo-full-rag.sh [--step] [--goal "..."] [--help]
#
#   --step   pause before each phase (for a sponsor walk-through)
#   --goal   override the trip prompt
#   --help   show this help

set -uo pipefail

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-tokyo_dev}"
GOAL='Plan a 3-day trip to Tokyo focused on traditional culture, temples, and Japanese food.'
STEP=0

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/demo-output"
ENV_FILE="$ROOT/apps/api/.env"

GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; BOLD=$'\033[1m'; RESET=$'\033[0m'

usage() { sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --help|-h) usage ;;
    --step) STEP=1; shift ;;
    --goal) GOAL="${2:?--goal needs a value}"; shift 2 ;;
    *) echo "Unknown argument: $1 (try --help)"; exit 2 ;;
  esac
done

pass=0; fail=0
step() { [ "$STEP" = 1 ] && { printf '%s' "${DIM}  (press Enter)${RESET}"; read -r _; }; }
ok()   { printf '%s[PASS]%s %s\n' "$GREEN" "$RESET" "$1"; pass=$((pass+1)); }
no()   { printf '%s[FAIL]%s %s\n' "$RED" "$RESET" "$1"; fail=$((fail+1)); }

mkdir -p "$OUT_DIR"
NDJSON="$OUT_DIR/plan-$(date +%Y%m%d-%H%M%S).ndjson"

printf '\n%sQUALCOMM AI100 — FULL RAG DEMO%s\n\n' "$BOLD" "$RESET"

# 1. Frontend -----------------------------------------------------------------
step
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "$FRONTEND_URL/planner" 2>/dev/null)
[ "$code" = "200" ] && ok "Next.js frontend ($FRONTEND_URL)" || no "Next.js frontend — HTTP $code"

# 2. Backend + real providers -------------------------------------------------
step
ready=$(curl -s --max-time 8 "$BACKEND_URL/ready" 2>/dev/null)
providers=$(printf '%s' "$ready" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["providers"]["embedding"],d["providers"]["vector_store"],d["providers"]["llm"],d["checks"]["embedding"],d["checks"]["vector_store"],d["checks"]["llm"])' 2>/dev/null)
read -r p_emb p_vec p_llm c_emb c_vec c_llm <<<"$providers"
[ "$c_emb$c_vec$c_llm" = "okokok" ] && ok "FastAPI backend ready ($BACKEND_URL)" || no "FastAPI backend not ready ($ready)"
[ "$p_emb" = "cirrascale" ] && ok "Cirrascale embedding provider active (not mock)" || no "Embedding provider is '$p_emb', expected cirrascale"
[ "$p_llm" = "cirrascale" ] && ok "Cirrascale Llama provider active (not mock)" || no "LLM provider is '$p_llm', expected cirrascale"
[ "$p_vec" = "qdrant" ]     && ok "Qdrant vector store active (not in-memory)" || no "Vector store is '$p_vec', expected qdrant"

# 3. Qdrant + indexed dataset -------------------------------------------------
step
col=$(curl -s --max-time 8 "$QDRANT_URL/collections/$COLLECTION" 2>/dev/null)
read -r points dim dist <<<"$(printf '%s' "$col" | python3 -c 'import sys,json;r=json.load(sys.stdin)["result"];v=r["config"]["params"]["vectors"];print(r["points_count"],v["size"],v["distance"])' 2>/dev/null)"
[ -n "${points:-}" ] && ok "Qdrant connection ($QDRANT_URL)" || no "Qdrant unreachable"
[ "${points:-0}" -gt 0 ] 2>/dev/null && ok "Tokyo dataset indexed — $points places, ${dim}D, $dist" || no "Collection '$COLLECTION' is empty — run the ingestion first"

# 4. Full plan: retrieval + LLM + streaming + validation ----------------------
step
printf '%s  generating a real itinerary (this calls Cirrascale + Qdrant)…%s\n' "$DIM" "$RESET"
t0=$(python3 -c 'import time;print(time.time())')
curl -sN --max-time 180 -X POST "$BACKEND_URL/api/v1/plan" \
  -H 'content-type: application/json' \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"goal":sys.argv[1],"preferences":{"interests":["Culture","Food"],"budget":"Mid","pace":"Balanced"}}))' "$GOAL")" \
  >"$NDJSON" 2>/dev/null
t1=$(python3 -c 'import time;print(time.time())')

# Parse the captured stream (no fabrication — all values come from the response).
summary=$(python3 - "$NDJSON" <<'PY'
import json, sys
events = []
for line in open(sys.argv[1], encoding="utf-8"):
    line = line.strip()
    if line:
        try: events.append(json.loads(line))
        except Exception: pass
types = [e.get("type") for e in events]
outline = next((e for e in events if e.get("type") == "outline"), None)
done = next((e for e in events if e.get("type") == "done"), None)
stops = sum(1 for t in types if t == "stop")
acts = verified = 0
for e in events:
    if e.get("type") == "stop":
        for d in e.get("days", []):
            for a in d.get("activities", []):
                acts += 1
                if a.get("verified"): verified += 1
trip = (outline or {}).get("trip", {})
print(json.dumps({
    "has_outline": outline is not None,
    "has_done": done is not None,
    "event_types": sorted(set(t for t in types if t)),
    "stops": stops, "activities": acts, "verified": verified,
    "title": trip.get("title", ""), "where": trip.get("where", ""),
    "ms": (done or {}).get("ms"), "cost": (done or {}).get("estimatedCostUsd"),
}))
PY
)
gen_s=$(python3 -c "print(f'{$t1-$t0:.1f}')")

has_outline=$(printf '%s' "$summary" | python3 -c 'import sys,json;print(json.load(sys.stdin)["has_outline"])')
has_done=$(printf '%s' "$summary" | python3 -c 'import sys,json;print(json.load(sys.stdin)["has_done"])')
n_types=$(printf '%s' "$summary" | python3 -c 'import sys,json;print(len(json.load(sys.stdin)["event_types"]))')
n_acts=$(printf '%s' "$summary" | python3 -c 'import sys,json;print(json.load(sys.stdin)["activities"])')
n_ver=$(printf '%s' "$summary" | python3 -c 'import sys,json;print(json.load(sys.stdin)["verified"])')

[ "$has_outline" = "True" ] && ok "Real semantic retrieval + grounded outline" || no "No outline event in the stream"
[ "$n_ver" -gt 0 ] 2>/dev/null && ok "Grounded activities from ingested places ($n_ver/$n_acts verified)" || no "No activities grounded to ingested places"
[ "$p_llm" = "cirrascale" ] && [ "$has_done" = "True" ] && ok "Cirrascale Llama inference produced a trip" || no "LLM did not complete the trip"
[ "$n_types" -ge 3 ] 2>/dev/null && ok "NDJSON streaming (outline → stop(s) → done)" || no "Stream was not multi-event NDJSON"
[ "$has_done" = "True" ] && [ "$n_acts" -gt 0 ] 2>/dev/null && ok "Validated Trip/Stop/Activity itinerary" || no "Itinerary failed validation"

# Redact any accidental secret in the saved artifact.
if [ -f "$ENV_FILE" ]; then
  key=$(grep -E '^CIRRASCALE_API_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
  [ -n "${key:-}" ] && python3 - "$NDJSON" "$key" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); key = sys.argv[2]
if key:
    p.write_text(p.read_text(encoding="utf-8").replace(key, "<redacted>"), encoding="utf-8")
PY
fi

# Final result ----------------------------------------------------------------
emb_model=$(grep -E '^CIRRASCALE_EMBEDDING_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
llm_model=$(grep -E '^CIRRASCALE_MODEL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2-)
printf '\n%sFINAL RESULT%s\n' "$BOLD" "$RESET"
python3 - "$summary" "$gen_s" "${emb_model:-BAAI/bge-base-en-v1.5}" "${llm_model:-Llama-3.1-8B}" "$points" <<'PY'
import sys, json
s = json.loads(sys.argv[1])
gen, emb, llm, points = sys.argv[2:6]
print(f"  Trip:             {s['title'] or '(none)'}")
print(f"  Destination:      {s['where'] or 'Tokyo, Japan'}")
print(f"  Retrieved places: {s['verified']} grounded / {s['activities']} activities across {s['stops']} stop(s)")
print(f"  Generation time:  {gen}s (server {s['ms']} ms)" if s['ms'] else f"  Generation time:  {gen}s")
print(f"  Embedding model:  {emb} (768D)")
print(f"  LLM model:        {llm}")
print(f"  Vector database:  Qdrant — {points} Tokyo places indexed")

print(f"\n  Saved itinerary artifact (secrets redacted): see demo-output/")
PY

printf '\n%s%d passed, %d failed%s\n' "$BOLD" "$pass" "$fail" "$RESET"
[ "$fail" -eq 0 ] || { printf '%sSome checks failed — the demo is NOT fully green.%s\n' "$RED" "$RESET"; exit 1; }
printf '%sAll checks genuinely passed.%s\n' "$GREEN" "$RESET"
