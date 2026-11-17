#!/usr/bin/env bash
#
# demo-backend.sh — Sponsor demo of the Qualcomm AI100 Prompt-to-Plan backend.
#
# Shows the real FastAPI backend: health/readiness, RAG architecture, live
# Cirrascale LLM inference, structured itinerary generation, and NDJSON
# streaming. Nothing is faked — every number comes from an actual API response.
#
# Usage:
#   ./scripts/demo-backend.sh --live      # require real Cirrascale LLM inference
#   ./scripts/demo-backend.sh --mock      # deterministic mock providers
#   ./scripts/demo-backend.sh --live --step   # pause between stages
#
set -euo pipefail

# ---- locate repo root (script works from anywhere) ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$ROOT/apps/api"
cd "$ROOT"

# ---- defaults ----
MODE="live"                       # sponsor-facing default; --mock for deterministic
STEP=0
BASE="${DEMO_BACKEND_URL:-http://localhost:8000}"
GOAL="Plan a 3-day trip to Tokyo, Japan, focused on culture and food."
INTERESTS="Culture,Food"
BUDGET="Mid"
PACE="Balanced"
USE_COLOR=1
STARTED_OWN=0
OWN_PORT=""

usage() {
  cat <<EOF
demo-backend.sh — demonstrate the Cirrascale Planner FastAPI backend

USAGE:
  ./scripts/demo-backend.sh [--live | --mock] [options]

MODES:
  --live     Require real Cirrascale LLM inference (mock embeddings/retrieval are
             allowed until those services exist). Fails clearly if the LLM is mock.
  --mock     Use deterministic mock providers (no API key needed). [default: --live]

OPTIONS:
  --step             Pause for Enter between stages (good for presenting).
  --goal "<text>"    Override the trip prompt.
  --url  <url>       Backend base URL (default: $BASE).
  --no-color         Disable ANSI colors.
  -h, --help         Show this help.

BEHAVIOUR:
  If a compatible backend is already running it is reused. Otherwise a dedicated
  one is started on a free port for this run and stopped on exit. An already
  running backend is never killed or reconfigured.

ARTIFACTS:
  Saved under demo-output/<timestamp>/ (git-ignored): raw NDJSON, reconstructed
  trip JSON, a human summary, and the provider config (secrets redacted).
EOF
}

# ---- args ----
while [[ $# -gt 0 ]]; do
  case "$1" in
    --live) MODE="live" ;;
    --mock) MODE="mock" ;;
    --step) STEP=1 ;;
    --goal) GOAL="$2"; shift ;;
    --url)  BASE="$2"; shift ;;
    --no-color) USE_COLOR=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
  shift
done
BASE="${BASE%/}"

# ---- colors ----
if [[ $USE_COLOR -eq 1 && -t 1 ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; CYAN=$'\033[36m'; MAG=$'\033[35m'
  export DEMO_COLOR=1
else
  BOLD=""; DIM=""; RESET=""; GREEN=""; YELLOW=""; RED=""; CYAN=""; MAG=""
  export DEMO_COLOR=0
fi
ok(){ echo "  ${GREEN}✓${RESET} $*"; }
warn(){ echo "  ${YELLOW}●${RESET} $*"; }
err(){ echo "  ${RED}✗${RESET} $*"; }
info(){ echo "  ${DIM}$*${RESET}"; }
heading(){ echo; echo "${BOLD}${CYAN}━━ $* ━━${RESET}"; echo; }
pause(){ if [[ $STEP -eq 1 ]]; then echo; read -r -p "  ${DIM}press Enter to continue…${RESET}" _; fi; }

# ---- small JSON helpers (python3, no jq dependency) ----
jget(){ python3 -c "import sys,json; d=json.load(sys.stdin); print(eval('d'+sys.argv[1]))" "$1" 2>/dev/null; }

backend_up(){ curl -fsS -o /dev/null --max-time 3 "$BASE/health" 2>/dev/null; }

provider_llm(){ curl -fsS --max-time 5 "$BASE/ready" 2>/dev/null | jget "['providers']['llm']"; }
llm_check(){ curl -fsS --max-time 5 "$BASE/ready" 2>/dev/null | jget "['checks']['llm']"; }

free_port(){
  for p in 8000 8010 8011 8012 8013 8020; do
    if ! lsof -ti "tcp:$p" >/dev/null 2>&1; then echo "$p"; return; fi
  done
  echo 8099
}

cleanup(){
  if [[ $STARTED_OWN -eq 1 && -n "$OWN_PORT" ]]; then
    lsof -ti "tcp:$OWN_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
    info "stopped the demo-managed backend on :$OWN_PORT"
  fi
}
trap cleanup EXIT

start_own(){
  local mode="$1" port env_llm
  port="$(free_port)"
  OWN_PORT="$port"
  local log="$OUTDIR/backend.log"
  info "starting a dedicated ${mode} backend on :$port (uv + uvicorn)…"
  if [[ "$mode" == "live" ]]; then env_llm="cirrascale"; else env_llm="mock"; fi
  ( cd "$API_DIR" && \
    EMBEDDING_PROVIDER=mock VECTOR_STORE_PROVIDER=memory LLM_PROVIDER="$env_llm" \
    CORS_ORIGINS=http://localhost:3000 \
    uv run uvicorn app.main:app --port "$port" >"$log" 2>&1 & )
  STARTED_OWN=1
  BASE="http://localhost:$port"
  local i
  for i in $(seq 1 40); do backend_up && break; sleep 0.5; done
  if ! backend_up; then
    err "backend failed to start — last log lines:"; tail -8 "$log" | sed 's/^/      /'
    exit 1
  fi
}

ensure_backend(){
  if backend_up; then
    local llm; llm="$(provider_llm)"
    if [[ "$MODE" == "live" ]]; then
      if [[ "$llm" == "cirrascale" ]]; then
        ok "reusing the running backend at $BASE (live: llm=cirrascale)"
      else
        warn "a backend is running at $BASE in '${llm}' LLM mode — leaving it untouched."
        start_own live
      fi
    else
      if [[ "$llm" == "mock" ]]; then
        ok "reusing the running backend at $BASE (mock)"
      else
        warn "running backend is '${llm}' LLM; starting a deterministic mock backend instead."
        start_own mock
      fi
    fi
  else
    info "no backend reachable at $BASE — starting one for this demo."
    start_own "$MODE"
  fi
}

# ======================================================================
echo
echo "${BOLD}${MAG}  Qualcomm AI100 · Prompt-to-Plan — Backend Demo${RESET}"
echo "${DIM}  FastAPI · RAG · Cirrascale LLM · structured streaming itineraries${RESET}"
echo "${DIM}  mode: ${RESET}${BOLD}${MODE}${RESET}"

TS="$(date +%Y%m%d-%H%M%S)"
OUTDIR="$ROOT/demo-output/$TS"
mkdir -p "$OUTDIR"

# ---------- Stage 1: health ----------
heading "Stage 1 · Backend health & providers"
info "Shows the backend is live and which components are real vs. mock."
ensure_backend
echo
echo "  ${BOLD}/health${RESET}"; curl -fsS "$BASE/health" | python3 -m json.tool | sed 's/^/    /'
echo "  ${BOLD}/ready${RESET}";  curl -fsS "$BASE/ready"  | python3 -m json.tool | sed 's/^/    /'
LLM="$(provider_llm)"; LLMCHK="$(llm_check)"
echo
if [[ "$LLM" == "cirrascale" ]]; then ok "LLM provider: ${BOLD}cirrascale${RESET} (REAL inference)"; else warn "LLM provider: ${LLM} (mock)"; fi
warn "Embedding provider: mock  — real Cirrascale embedding service not available yet"
warn "Vector store: memory (fixtures)  — Qdrant + scraper data pending"
if [[ "$MODE" == "live" && "$LLM" != "cirrascale" ]]; then
  err "Live mode requires real Cirrascale LLM inference, but the backend reports llm='${LLM}'."
  info "Start the backend with LLM_PROVIDER=cirrascale + CIRRASCALE_API_KEY, or run with --mock."
  exit 3
fi
if [[ "$MODE" == "live" && "$LLMCHK" != "ok" ]]; then
  err "Live LLM is selected but credentials check = '${LLMCHK}'. Set CIRRASCALE_API_KEY in apps/api/.env."
  exit 3
fi
pause

# ---------- Stage 2: architecture ----------
heading "Stage 2 · RAG architecture"
real="${GREEN}● real${RESET}"; mock="${YELLOW}○ mock${RESET}"
cat <<EOF
  User Prompt
      |
      v
  FastAPI /api/v1/plan            ${real}  (Pydantic-validated request)
      |
      v
  Embedding Provider              ${mock}  (deterministic; Cirrascale model pending)
      |
      v
  Vector Store / Retrieval        ${mock}  (in-memory fixtures; Qdrant + scraper pending)
      |
      v
  Context Assembly                ${real}  (retrieved places -> grounded prompt)
      |
      v
  Cirrascale LLM                  $([[ "$LLM" == cirrascale ]] && echo "$real  (Llama-3.1-8B on AI100)" || echo "$mock  (deterministic)")
      |
      v
  Validated Trip JSON             ${real}  (Pydantic schema; invalid places flagged)
      |
      v
  NDJSON Streaming                ${real}  (outline -> stop x N -> done)
EOF
info "The contract (schemas, OpenAPI->TS) is shared with the frontend; see docs/api-contract.md."
pause

# ---------- Stage 3-5: live generation + summary + artifacts ----------
heading "Stage 3 · Live itinerary generation (streaming)"
info "Calling the real /api/v1/plan and printing events as they arrive."
REQ_FLAG=""; [[ "$MODE" == "live" ]] && REQ_FLAG="--require-live"
set +e
python3 "$SCRIPT_DIR/demo_stream.py" \
  --url "$BASE" --goal "$GOAL" \
  --interests "$INTERESTS" --budget "$BUDGET" --pace "$PACE" \
  --outdir "$OUTDIR" $REQ_FLAG
GEN_RC=$?
set -e
pause

heading "Stage 4 · Results"
if [[ $GEN_RC -eq 0 ]]; then
  ok "Generation complete and schema-valid."
else
  err "Generation did not complete cleanly (rc=$GEN_RC). See artifacts for details."
fi
echo
echo "${BOLD}Stage 5 · Artifacts${RESET} ${DIM}(git-ignored)${RESET}"
for f in providers.json stream.ndjson trip.json summary.txt sources.txt; do
  [[ -f "$OUTDIR/$f" ]] && info "demo-output/$TS/$f"
done

# ---------- wrap up ----------
heading "Done · What this demonstrates"
ok "FastAPI backend is operational (health/ready, validated requests)."
[[ "$LLM" == cirrascale ]] && ok "Real Cirrascale LLM inference (Llama-3.1-8B) generating itineraries." \
                           || warn "LLM ran in mock mode (use --live for real inference)."
ok "Structured, Pydantic-validated trips streamed as NDJSON (outline -> stop -> done)."
ok "Shared request/response contract with the frontend (OpenAPI -> TypeScript)."
echo
echo "  ${BOLD}Remaining integrations${RESET}"
warn "Cirrascale embedding model (endpoint / model id / vector dim) — provider is stubbed."
warn "Qdrant vector store + scraper JSONL ingestion — contract + CLI ready, data pending."
info "All of the above swap in by configuration only (env), no backend rewrite."
echo
exit $GEN_RC
