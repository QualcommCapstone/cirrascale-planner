# Frontend Architecture — planner UI

> Agent steering doc. How the landing page and the `/planner` travel-planning
> surface are built (SCRUM-55).

## One-liner

A trip is shown as **places you can see**, not a plan as text. The user types one
sentence (plus optional interest/budget/pace chips); the server generates the trip
in stages and **streams** it: the outline (stops, route, where to stay/eat) arrives
first, then each stop's day-by-day plan. Every activity is checked against
Wikipedia for real coordinates and a free-licensed photo. The UI is a scrolling
photo-led story with the globe fixed alongside it.

## Data flow

```
TripComposer / SampleTrips / landing ?q=
   │  planTrip(goal, preferences)                         src/lib/trip/client.ts
   ▼
POST /api/itinerary { goal, preferences }  ──►  generateTrip()   src/lib/trip/generate.ts
   │                                              1. outline prompt  (retry once on issues)
   │                                              2. locate stops on Wikipedia
   │  NDJSON stream                               3. emit "outline"
   │  outline → stop × N → done                   4. per stop (parallel): days in 2-day chunks
   ▼                                                 (retry once) → verify places → emit "stop"
useTrip (Zustand)  src/lib/store/trip.ts          5. emit "done" { ms }
   │ trip, pendingStopIds, focus/hover
   ├──► TripStory  (overview, stop sections, activity cards, transit connectors)
   └──► ItineraryGlobe (numbered stops, activity pins, route drawn leg by leg)
```

Card ↔ globe sync goes through the store: `focusStop` / `focusActivity` /
`hoverActivity`. `focusSource` says who asked — `"globe"` makes the story scroll to
the item, any focus makes the globe fly; `focusTick` lets a re-click re-trigger.

## Key files

| File | Role |
| --- | --- |
| `src/app/page.tsx`, `src/components/landing/*` | Landing: rotating photo hero, prompt box as CTA (→ `/planner?q=`), real proof chips, sample trips. |
| `src/lib/destinations.ts` | Curated hero/sample destinations: Wikimedia photo + matching prompt. |
| `src/components/layout/AppShell.tsx` | `/planner` layout (globe left, story right; stacked on mobile). Opens `#trip=` share links and `?q=` prompts. |
| `src/components/layout/Header.tsx` | Brand, trip title, New trip / Share / Save PDF. |
| `src/components/trip/TripStory.tsx` | Welcome → progress → trip story. |
| `src/components/trip/TripOverview.tsx` | Headline + muted "— where", summary, vibe tags, Where/When/Days/Route, stop photo strip, "Planned for" chips, real generation time. |
| `src/components/trip/StopSection.tsx` | Stop hero photo card, Stay/Eat tiles, one block per day. |
| `src/components/trip/ActivityCard.tsx` | Photo card: slot tag, location tag, title, one-line reason, duration/cost/category, Wikipedia link, "Not verified" badge. |
| `src/components/trip/TransitConnector.tsx` | "Tokyo → Kyoto · 2h 15m train" between stops. |
| `src/components/trip/PreferenceChips.tsx` | Interests (multi), budget, pace. |
| `src/components/globe/ItineraryGlobe.tsx` | react-globe.gl: land polygons, numbered stop markers, activity pins (zoomed in only), route arcs, camera fly-to. |
| `src/lib/trip/types.ts` | Trip schema + request/event types (zod for the request). |
| `src/lib/trip/normalize.ts` | Lenient zod parsing of model JSON, day numbering, leg plausibility, finalize (drop/blank what's still bad). |
| `src/lib/trip/quality.ts` | Filler / generic-name / duplicate checks; issues are fed back on retry. |
| `src/lib/trip/places.ts` | Wikipedia verification + photos (no key). |
| `src/lib/trip/share.ts`, `format.ts` | Share-link encode/decode (validated), display helpers, `safeUrl`. |
| `src/lib/planner.ts` | All prompts (outline + per-stop days). |

## Content rules (why the output isn't filler)

- **Small calls:** one outline call, then each stop's days 2 at a time. 8B drops days
  and loops when asked for more; `extractArrayItems` salvages complete days from a
  truncated, looping answer.
- **Quality gate:** filler phrases ("explore the city", "a great place to"…), names
  that are instructions or categories ("Visit a temple", "Local market"), reasons
  under 6 words or starting with "Visit", headlines repeating the city, duplicates.
  One retry with the problems listed; whatever still fails is dropped or blanked.
- **Legs:** the model's duration is kept only if plausible for the straight-line
  distance; otherwise it's estimated and shown with "≈".
- **No duplicates:** back-to-back stops in one city are merged; a food pick that
  became an activity leaves the Eat tile; two names resolving to the same
  Wikipedia article keep only the first.

## Places & photos (Wikipedia)

Per stop: one `geosearch` (≤500 articles within 10 km), names matched locally, a
few full-text searches for places farther out (day trips, ≤40 km), and one batched
request for photos. A place is **verified** only when an article title matches the
name (distinctive words both ways, same kind of place — a market isn't a station)
and lies within 40 km. Verified places get real coordinates (globe pins) and the
article's lead image; unverified ones are flagged, get no pin, and use a
neighborhood or city photo. Logos/maps/SVGs are never used as photos.

Wikimedia etiquette: descriptive User-Agent (repo URL), ≤2 concurrent requests,
back off on 429 using `Retry-After`, cache successful lookups in memory.

## Design system

- Light, airy, photo-first; tokens in `src/app/globals.css` (light + dark): warm
  off-white surfaces, near-black ink (`primary` = ink pill buttons) and one warm
  accent `--brand` for the route, pins, focus and highlights. Globe colors mirror
  these in `src/lib/theme.ts` (three.js can't read CSS vars).
- Type: Inter (`font-sans`) for UI/body, Inter Tight (`font-display`) bold for
  headlines. Large radii (`rounded-xl` cards). `.photo-scrim` for text on photos.
- Brand name everywhere: **Cirrascale Planner**.

## Conventions specific to this surface

- The globe is **client + dynamic only** — never import `react-globe.gl` or `three`
  in a server component.
- Shared trips (`#trip=`) are untrusted: `decodeTrip` validates the shape with zod,
  and every `href`/`src` from trip data goes through `safeUrl` (https only).
- Wikimedia images are plain `<img>` (already sized; no optimizer/remotePatterns).
- Streaming: the route only returns NDJSON; client parsing is `readEvents`.

## Responsiveness, a11y, print

- Desktop: globe 42–44% left, story scrolls right. ≤ md: 34vh globe strip on top.
- Cards keep their links usable: a full-card button for "show on map" sits under
  the credit/Wikipedia links. Chips are real toggle/radio buttons. Globe canvas is
  `aria-hidden`; the story is its text equivalent.
- Save PDF = `window.print()` with a print stylesheet (story only, no chrome).

## Known limits / next

- English Wikipedia only: real places filed under another name (e.g. National
  Pantheon → "Church of Santa Engrácia") stay unverified. Wikidata aliases would help.
- Restaurants/bars rarely have articles, so they're often "Not verified".
- The 110m country outlines look coarse when zoomed into a city; a tile map for the
  city view would be the next step.
- Personalization is per-request chips; saved preferences + retrieval is SCRUM-6.

## Legacy

The original markdown chat lives at `/planner/chat` (still uses `/api/plan`),
unlinked from the main nav. The OpenUI detail panel (`/api/chat`) was removed: the
richer cards now carry that content.
