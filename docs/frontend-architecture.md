# Frontend Architecture — planner UI

> Agent steering doc. How the `/planner` travel-planning surface is built.

## One-liner

`/planner` is a Linear-inspired, dark-charcoal UI with an interactive 3D
wireframe globe on the left and a structured itinerary panel on the right. A
Cirrascale-backed endpoint returns a structured itinerary (JSON); Zustand holds
it; the globe and panel render from that state. An OpenUI panel layers
AI-generated components on top (see `openui-integration.md`).

## Data flow

```
TripComposer  ──POST /api/itinerary { goal }──►  Cirrascale (complete, 8B)
      │                                               │  strict-JSON prompt
      │                                        extractJson + geo fallback + validate
      ▼                                               ▼
  useItinerary (Zustand)  ◄────────────────  { title, destinations[] }
      │                 │
      │ destinations    │ focusedId
      ▼                 ▼
 ItineraryGlobe     ItineraryPanel (cards)  ──click──►  focus(id)  ──►  globe flies
 (markers, arcs)                              AiItinerary ──POST /api/chat──► Cirrascale
```

## Key files

| File | Role |
| --- | --- |
| `src/app/planner/page.tsx` | Renders `<AppShell/>`. |
| `src/components/layout/AppShell.tsx` | Nav rail + header + globe/panel split; mobile tab toggle. |
| `src/components/layout/{NavRail,Header}.tsx` | Persistent chrome. |
| `src/components/globe/GlobeClient.tsx` | `dynamic(ssr:false)` wrapper (keeps three.js off the server). |
| `src/components/globe/ItineraryGlobe.tsx` | react-globe.gl: graticule grid, hex-dotted land, glowing markers, route arcs, click-to-focus + camera, reduced-motion aware. |
| `src/lib/store/itinerary.ts` | Zustand store + `selectArcs` / `selectFocused`. |
| `src/app/api/itinerary/route.ts` | Cirrascale → structured itinerary JSON. |
| `src/lib/{planner,json,geo,theme}.ts` | Itinerary prompt, JSON extraction, coord fallback, globe colors. |
| `src/components/trip/*` | Composer, cards, panel, OpenUI AI panel. |

## Design system

- Tokens in `src/app/globals.css` for **both** light and dark (charcoal + lavender,
  1px borders). Inter via `next/font` in `layout.tsx`. `defaultTheme="dark"`.
- Reuse tokens (`bg-background`, `text-foreground`, `border-border`, `text-primary`)
  and `cn()`; `.transition-smooth` for micro-interactions. Reduced-motion honored
  globally (CSS) and in the globe (no auto-rotate / instant camera).

## Conventions specific to this surface

- The globe is **client + dynamic only** — never import `react-globe.gl` or `three`
  in a server component.
- All itinerary mutations go through the Zustand actions; components read via
  selectors to avoid re-renders.
- Model note: `Llama-3.1-70B` returns 429 ("model not configured") on the free
  tier — use the default `Llama-3.1-8B`. The strict-JSON prompt + server-side
  validation + `geo.ts` fallback make 8B reliable enough for the globe.

## Responsiveness & a11y

- Desktop: globe + 380px side panel. ≤ md: single pane with a `Map | Itinerary`
  tab toggle (`AppShell`).
- Landmarks (`nav`/`main`/`aside`), aria-labels on icon buttons, lavender
  focus-visible rings, cards are real buttons (keyboard-operable). The globe
  `<canvas>` is `aria-hidden`; the itinerary panel is its text equivalent.

## Legacy

The original markdown chat lives at `/planner/chat` (still uses `/api/plan`),
unlinked from the main nav.
