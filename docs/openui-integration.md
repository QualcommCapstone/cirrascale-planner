# OpenUI Integration

> Agent steering doc. How OpenUI renders AI-generated itinerary components on top
> of the structured itinerary, and the tradeoffs.

## Why hybrid

Cirrascale is a **text-completions** API, not OpenAI chat, and the only available
model on the free tier is **Llama-3.1-8B** (70B → 429). OpenUI's full
`AgentInterface` chat framework assumes an OpenAI-style backend. So we use OpenUI
in a **lightweight, hybrid** way:

- The **structured itinerary** (`/api/itinerary` → Zustand → cards + globe) is the
  reliable source of truth. It always works.
- **OpenUI renders a detail panel on top** for the focused destination. If it
  produces nothing useful (small model) or throws, the structured cards remain.

## How it's wired

- **Client** (`src/components/trip/AiItineraryInner.tsx`):
  - `generateSystemPrompt({ library: openuiLibrary.toSpec(), promptOptions: openuiPromptOptions })`
    (`@openuidev/lang-core` + `@openuidev/react-ui`) builds the system prompt
    describing the component library — done **client-side** so `react-ui` never
    loads on the server.
  - Sends `systemPrompt + instruction` to `/api/chat`, gets text back, and renders
    it with `<Renderer response library={openuiLibrary} isStreaming={false} />`
    (`@openuidev/react-lang`).
  - Imports `@openuidev/react-ui/index.css` for component styles.
- **Server** (`src/app/api/chat/route.ts`): a thin proxy — `{ prompt }` →
  `complete()` (the one Cirrascale integration point) → `{ text }`. No OpenUI
  imports server-side.
- **Isolation** (`src/components/trip/AiItinerary.tsx`): `dynamic(ssr:false)` +
  `ErrorBoundary` so OpenUI is code-split and can never break the core page.

## Dependencies (why they're here)

`@openuidev/react-ui`, `@openuidev/react-lang`, `@openuidev/lang-core`, plus peers
that surfaced during integration: **`zustand@4`** (OpenUI peer — the app's own
store is v4-compatible), **`zod@4`** (lang-core uses `zod/v4/core`), and the
**`ai`** SDK (react-headless dependency).

## Known limitations

- **8B output is modest**: it emits thin/duplicated OpenUI Lang and sometimes
  leaks a style token as text (e.g. `large-heavy`). Acceptable because the
  structured cards carry the real content. A stronger model (70B, if enabled, or
  another provider) would improve this immediately — it's a model limit, not a
  wiring one.
- **Non-streaming** today (`complete()`), so the panel appears all at once. The
  `Renderer` supports `isStreaming`; add a `stream()` to `src/lib/cirrascale.ts`
  and switch `/api/chat` to a streamed `text/plain` response to enable it.

## To improve later

- Add streaming (above).
- Tighten the instruction in `AiItineraryInner` to steer 8B toward a single Card +
  list and away from style-token leakage.
- If a chat-completions-compatible model becomes available, the full
  `AgentInterface` becomes viable.
