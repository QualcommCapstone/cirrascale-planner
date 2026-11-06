# Agent Handoff — Cirrascale Planner

> Steering doc for any agent/human taking over. Snapshot of everything done so
> far, where it lives, how to run it, and what's open. Pair this with
> **[AGENTS.md](./AGENTS.md)** (entry point) and the `docs/` steering files.
>
> Last updated: 2026-11-06.

## 1. What this project is

A **travel/itinerary planner** built on the **Qualcomm AI Inference Suite**
(hosted by **Cirrascale**) as the only LLM backend. Started as a generic
"prompt → plan" tool; the team pivoted it to trip planning (see
`docs/features.md`). Main surface `/planner`: an interactive 3D globe + a
structured itinerary, with an OpenUI-rendered AI detail panel.

## 2. Repos & org

- GitHub org: **QualcommCapstone** (created in the browser; org creation isn't
  possible via API/CLI). Repos were transferred into it from a personal account.
- **cirrascale-planner** — main platform (this repo, Next.js 14).
  https://github.com/QualcommCapstone/cirrascale-planner
- **cirrascale-sandbox** — zero-dependency Node playground for the Cirrascale API
  (completion, streaming, plan, scrape-and-plan).
  https://github.com/QualcommCapstone/cirrascale-sandbox

## 3. Commit / attribution convention (important)

- Commit identity for this repo is set to **`RishithMody <rishithmody@gmail.com>`**
  (gmail is linked to the GitHub account → counts on the contribution graph).
- **Do NOT add `Co-Authored-By: Claude` trailers** to commits here.
- The 3 original scaffold commits were authored with `engineering@tryada.app`
  (an *unlinked* email) so they don't count on the graph; they weren't rewritten
  because teammates built on top (a rewrite would force-push and break clones). To
  credit them, verify that email on the GitHub account — don't rewrite history.

## 4. The LLM platform (one source of truth: `docs/cirrascale-platform.md`)

- `POST https://aisuite.cirrascale.com/apis/v2/completions`,
  `Authorization: Bearer $CIRRASCALE_API_KEY`,
  body `{ prompt, model, stream, max_tokens }` → `data.choices[0].text`.
- **Completions API, not chat** (single `prompt` string; no `messages`).
- **Model availability gotcha:** only **`Llama-3.1-8B`** is enabled on the free
  tier. `Llama-3.1-70B` returns **429 "model not configured"**. Default to 8B.
- Key is **server-only**. Local: `cirrascale-planner/.env.local`. CI: the repo
  secret `CIRRASCALE_API_KEY` (set from the local key).
- All inference goes through one function: `complete()` in `src/lib/cirrascale.ts`.

## 5. Branches & PRs

| Branch | PR | Contents | State |
| --- | --- | --- | --- |
| `main` | — | base (feature tracker, specs) | — |
| `feature/docker-cicd` | **#4** | Dockerfile, docker-compose, `/api/health`, `/api/ready`, GitHub Actions (build→test container→Trivy→GHCR), live Cirrascale smoke test | CI green |
| `feature/itinerary-globe-ui` | **#6** | the globe + itinerary UI, OpenUI panel, **and the Vitest suite + CI** | this handoff's branch |
| `SCRUM-51-ci-pipeline` | — | Drew's Vitest + lint/test workflow | not merged |
| `aayush/feature-list`, `SCRUM-48-*` | #1,#2 (merged) | feature tracker/docs | merged |

⚠️ **Known collision:** PR #4, PR #6, and Drew's branch each add
`.github/workflows/ci.yml` with different content — they will conflict on merge.
Reconcile into one workflow (lint/typecheck/test/build + the Docker/health/
Cirrascale-smoke stages) before/while merging.

## 6. What's built

### Docker / CI (PR #4 — `feature/docker-cicd`)
- Multi-stage `Dockerfile` (standalone Next output, non-root, `HEALTHCHECK`), OCI
  labels; `docker-compose.yml` for one-command demo runs.
- `/api/health` (liveness) and `/api/ready` (pings Cirrascale).
- Actions: validate (lint/tsc/build) → Docker buildx w/ layer cache → run container
  + health test → **live Cirrascale smoke test** (prints a generated plan to the
  job summary) → Trivy scan → publish to GHCR. Secret `CIRRASCALE_API_KEY` set.

### Globe + itinerary UI (PR #6 — `feature/itinerary-globe-ui`, this branch)
- **Design system** (`src/app/globals.css`, `layout.tsx`): Linear-inspired charcoal
  + lavender, light **and** dark, Inter, 1px borders, reduced-motion utilities.
- **State** (`src/lib/store/itinerary.ts`): Zustand store + `selectArcs` /
  `selectFocused`.
- **Structured itinerary** (`src/app/api/itinerary/route.ts` + `src/lib/itinerary.ts`
  + `json.ts` + `geo.ts`): Cirrascale → strict-JSON → extract → validate → coord
  fallback. Reliable on 8B.
- **Globe** (`src/components/globe/`): `react-globe.gl` wireframe (graticule grid,
  hex-dotted land, glowing markers, animated route arcs, click-to-focus + camera),
  dynamic/no-SSR, reduced-motion aware.
- **Layout** (`src/components/layout/`): nav rail + header + globe/panel split,
  responsive mobile tab toggle.
- **Itinerary panel** (`src/components/trip/`): composer, day-ranged cards, OpenUI
  AI detail panel.
- **OpenUI** (hybrid; `docs/openui-integration.md`): `/api/chat` proxy +
  `@openuidev/react-lang` `Renderer`, system prompt built client-side, dynamic +
  error-boundaried with the structured cards as fallback.
- **Tests + CI**: Vitest (31 tests) for json/geo/planner/itinerary/store;
  `.github/workflows/ci.yml` (npm ci → lint → tsc → test → build).
- Legacy markdown chat preserved at `/planner/chat` (uses `/api/plan`).

## 7. Steering docs (read these)
- `AGENTS.md` — entry point & golden rules.
- `docs/cirrascale-platform.md` — the LLM API (source of truth).
- `docs/architecture.md` — app wiring (original).
- `docs/frontend-architecture.md` — the globe + itinerary UI.
- `docs/openui-integration.md` — OpenUI hybrid design + limits.
- `docs/conventions.md` — code style, testing & CI.
- `docs/features.md` — feature tracker (Jira SCRUM-*).
- `.claude/skills/cirrascale-inference/` — skill for making model calls.

## 8. Run / test / build

```bash
# App (needs a key for planning; get one at aisuite.cirrascale.com)
cp .env.example .env.local        # add CIRRASCALE_API_KEY
npm install
npm run dev                       # http://localhost:3000 → /planner

# Tests / checks (no key needed)
npm test                          # 31 Vitest unit tests
npm run lint
npx tsc --noEmit
npm run build

# Docker (on feature/docker-cicd)
CIRRASCALE_API_KEY=... docker compose up --build   # http://localhost:3000
```

## 9. Open items / next steps
1. **Reconcile the three `ci.yml`** (PR #4, PR #6, Drew's branch) into one workflow.
2. **Merge order**: decide #4 vs #6 first; both touch CI. (#6 branched off `main`
   *before* #4's Docker changes, so `/api/health`/`/api/ready`/standalone output
   are **not** on #6 — rebase or merge to combine.)
3. **OpenUI quality** is limited by 8B (thin output, occasional leaked style token).
   A chat-capable or larger model would upgrade it with no code change. Consider
   adding streaming (`stream()` in `cirrascale.ts` + `text/plain` in `/api/chat`).
4. **GHCR publish** may need org package permissions enabled on first push.
5. Untracked local-only dir `qualcomm_test/` (an OpenUI scaffold) is excluded from
   this repo's tsconfig and not committed — ignore it.

## 10. Environment notes
- Node 20+ (CI uses 20; local dev used 26). npm (no pnpm).
- OpenUI pulled in peers: `zustand@4` (app store is v4-compatible), `zod@4`
  (lang-core needs `zod/v4/core`), and the `ai` SDK (react-headless dep).
