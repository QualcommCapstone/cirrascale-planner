# CLAUDE.md

Read **[AGENTS.md](./AGENTS.md)** first — it's the entry point and links the
steering docs (`docs/cirrascale-platform.md`, `docs/architecture.md`,
`docs/conventions.md`) and the `cirrascale-inference` skill.

Quick reminders:

- All LLM calls go through `complete()` in `src/lib/cirrascale.ts`.
- `CIRRASCALE_API_KEY` is server-only; never expose it to the browser.
- The platform is a **completions** API (`prompt` → `choices[0].text`), not chat.
- Keep changes basic and update the matching doc in the same commit.
