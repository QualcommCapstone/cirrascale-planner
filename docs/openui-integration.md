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
  - Sends the focused stop as `{ destination }` to `/api/chat`, gets text back,
    and renders it with `<Renderer response library={openuiLibrary} isStreaming={false} />`
    (`@openuidev/react-lang`).
  - Imports `@openuidev/react-ui/index.css` for component styles.
- **Server** (`src/app/api/chat/route.ts`): validates `destination` with zod
  (length-limited fields), builds the prompt, calls `complete()` (the one
  Cirrascale integration point) with a fixed `max_tokens`, and returns `{ text }`.
  - `src/lib/openui.ts`: builds (and caches) the system prompt with
    `generateSystemPrompt()`, describing only the 8 components a stop panel needs
    (Stack, Card, CardHeader, TextContent, ListBlock, ListItem, TagBlock,
    Separator) plus one panel-shaped example and our own rules (no images, use
    the given activities only). The full library is ~80 components / ~9k
    tokens; this is ~1.6k. The client still renders with the full library.
  - `src/lib/planner.ts`: `buildDetailPrompt()` appends the per-stop instruction
    and ends with `root = `, so the completion starts at the markup. Without it,
    8B continued the "Activities" data line and invented extra activities.
    `extractDetailMarkup()` restores that lead, drops anything after a code
    fence, and strips `#` comments (8B repeats one until `max_tokens`; the API
    ignores `stop`).
  - The client never sends a prompt, so the route can't be used as a general
    completion proxy for our key.
  - `next.config.mjs` lists `@openuidev/react-ui` in
    `serverComponentsExternalPackages`: it's a client-boundary package, and Next
    won't bundle it into a server route otherwise.
- **Isolation** (`src/components/trip/AiItinerary.tsx`): `dynamic(ssr:false)` +
  `ErrorBoundary` (keyed on the focused stop, so it resets on switch) so OpenUI
  is code-split and can never break the core page.

## Dependencies (why they're here)

`@openuidev/react-ui`, `@openuidev/react-lang`, `@openuidev/lang-core`, plus peers
that surfaced during integration: **`zustand@4`** (OpenUI peer — the app's own
store is v4-compatible), **`zod@4`** (lang-core uses `zod/v4/core`), and the
**`ai`** SDK (react-headless dependency).

## Known limitations

- **8B output is modest**: with the trimmed prompt it reliably produces a clean
  Card + list (0 parser errors in live tests, ~4–9s), but the panel mostly
  restates the itinerary card plus a one-line subtitle per activity, and those
  subtitles are unverified model text. A stronger model (70B, if enabled) or
  richer input data (weather, prices, retrieval results) is what would make
  the panel add real information.
- **Non-streaming** today (`complete()`), so the panel appears all at once. The
  `Renderer` supports `isStreaming`; add a `stream()` to `src/lib/cirrascale.ts`
  and switch `/api/chat` to a streamed `text/plain` response to enable it.

## To improve later

- Add streaming (above).
- Feed the panel richer data than the card already shows, and add the
  components to `PANEL_COMPONENTS` in `openui.ts` that it then needs.
- If a chat-completions-compatible model becomes available, the full
  `AgentInterface` becomes viable.
