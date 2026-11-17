# CLAUDE.md

Read **[AGENTS.md](./AGENTS.md)** first — it's the entry point and links the
steering docs (`docs/cirrascale-platform.md`, `docs/architecture.md`,
`docs/conventions.md`) and the `cirrascale-inference` skill.

## Project Spec

- Read `docs/sponsor-spec.md` before planning any feature or architecture work.
- The spec is the sponsor's original text. Never edit it.
- Where the spec and team decisions differ, "Agreed changes from the original
  spec" (below) wins.
- Before finishing a plan, check it against the spec's pipeline: preference
  capture → retrieval/ranking → itinerary generation → visual presentation →
  iteration/refinement. Flag anything that drifts from it.

## Agreed changes from the original spec

- Visual itinerary uses real place photos (Wikipedia/Wikimedia) instead of an
  image model. *Pending sponsor confirmation.*

Quick reminders:

- All LLM calls go through `complete()` in `src/lib/cirrascale.ts`.
- `CIRRASCALE_API_KEY` is server-only; never expose it to the browser.
- The platform is a **completions** API (`prompt` → `choices[0].text`), not chat.
- Keep changes basic and update the matching doc in the same commit.
