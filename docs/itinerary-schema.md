# Itinerary Schema — the LLM → UI contract

> Agent steering doc. This is the single source of truth for the shape of an
> itinerary. The generation prompt, the validator, and every UI component build
> against it. If you change a field, update this file in the same commit.
>
> Ticket: [SCRUM-52](https://qualcomm-ai100-travel.atlassian.net/browse/SCRUM-52) ·
> `schema_version: "1"` · Status: **draft, pending team review**

## Glossary

Plain-language meanings for the terms used in this doc.

**Schema basics**

| Term | Meaning |
| ---- | ------- |
| Schema | The agreed shape of the data: which fields exist, what type each one is, and which are required. |
| Field | One named piece of data, like `title` or `pace`. |
| Required (✓) / optional | A required field must always be present. An optional field can be left out, and the itinerary is still valid. |
| Enum | A field that only accepts values from a fixed list. For example, `pace` must be `relaxed`, `moderate`, or `packed`, and nothing else. |
| `schema_version` | Which version of this schema the data follows. When we make a change that would break old data, the number goes up so the code knows how to read older itineraries. |
| `id` | A permanent, unique label for an itinerary, day, or activity (e.g. `act_77b0`). It never changes, even when items are reordered, so edits can point at the exact item. |

**Who fills a field (owners)**

| Term | Meaning |
| ---- | ------- |
| LLM | The language model. It writes the creative parts of the plan: titles, descriptions, which activities to do. |
| BE (backend) | Our server code. It handles bookkeeping like IDs, timestamps, and attaching the user's request. |
| Tool | An outside data source, like a places API, an image model, or a price lookup. It supplies real-world facts. |
| Enrichment | The step where tools add facts (address, coordinates, cost, photos) to an LLM-written plan. |
| Verified | An activity whose place a tool has confirmed exists, with a source link attached. Until then it is unverified. |

**Trip and planning terms**

| Term | Meaning |
| ---- | ------- |
| Pace | How full and busy each day feels. `relaxed` means a few activities with plenty of downtime, `moderate` is balanced, and `packed` fits in as much as possible. It sets how many activities a day gets unless the user picks a number. |
| `activities_per_day` | The user's "things per day" filter. When set, it overrides pace and fixes the number of activities each day. |
| Travelers | Who is going: number of adults and each child's age. Used to plan around things like naps and strollers. |
| Time slot | The rough part of the day an activity happens in: `morning`, `afternoon`, or `evening`. Exact times are optional. |
| Category | The one main type of an activity (food, outdoors, excursion, etc.). It picks the card's icon and color. |
| Tags | Extra labels an activity can have several of, like `kid-friendly` or `reservation-needed`. Used for filters and badges. |
| Rank | How important an activity is within its day. 1 is the top pick. Trimming keeps the best-ranked ones. |
| Alternatives | Activities kept in reserve for a day, usually ones cut by trimming. They can be swapped back in without asking the LLM again. |
| Trimming | Cutting a day down to fewer activities (e.g. 5 → 3) while keeping the best ones and re-timing the day. |
| Refinement | Changing an existing plan based on a follow-up request, like "make day 2 more relaxed", instead of starting over. |

**Formats and standards**

| Term | Meaning |
| ---- | ------- |
| JSON | The text format the data is written in, made of `"name": value` pairs inside `{ }`. |
| ISO date | A date written as `YYYY-MM-DD`, e.g. `2026-11-14`. |
| ISO 8601 datetime | A date and time written as `2026-11-01T18:00:00Z`. The `Z` means UTC. |
| ISO 4217 | Standard 3-letter currency codes, e.g. `USD`, `EUR`. |
| `place_id` | The ID a places API (like Google Places) uses for a real location. Having one means the place was looked up and confirmed. |
| Alt text | A short text description of an image, read aloud by screen readers for users who can't see it. |
| Image prompt | The text description sent to the image model to generate a picture. |

**Validation terms**

| Term | Meaning |
| ---- | ------- |
| Validation | Checking that the LLM's output matches this schema before anyone sees it. |
| Hard rule | A check that must pass. If it fails, the system asks the LLM once more, then shows an error. |
| Soft rule | A check that is recorded for evaluation but doesn't block the plan from showing. |
| Breaking change | A schema change that would make existing data or code stop working, like renaming or removing a field. Adding an optional field is not breaking. |

## Design rules

1. **Each field has one owner.** A field is filled by the **LLM**, by the
   **backend**, or by a **tool** (places API, image model, cost lookup). The LLM
   is only asked for its own fields. That keeps the prompt small (it matters for
   8B models) and enforces the rule in `feature-architecture.md`: *the LLM never
   invents a place, a price, or a source.*
2. **Tool fields are optional in v1.** The MVP is LLM-only, so an itinerary with
   no tool fields is still valid and renders. Enrichment fills them in later
   without a schema change.
3. **Stable IDs on days and activities.** Drag-and-drop, edit-by-chat ("swap
   that dinner"), and React keys all need them. The backend assigns IDs after
   validation, never the LLM.
4. **Meals are activities** with `category: "food"`, not a separate `meals`
   block. One list per day means one card type, one drag-and-drop list, and one
   edit path.
5. **Strict validation.** Unknown fields are dropped. Anything that fails
   validation never reaches the UI (retry once, then show an error).
6. **Verified vs. unverified.** An activity counts as verified when it has
   `location.place_id` and `source`. In the MVP (LLM-only) nothing is verified
   yet, so the UI shows activities with an "unverified" label. Once the
   verifier exists, the rule in `feature-architecture.md` applies: facts with
   no source are not shown.

Owner key used below: **LLM** · **BE** (backend) · **Tool**. "Req" = required.

## Itinerary (root)

| Field            | Type              | Req | Owner | Notes                                         |
| ---------------- | ----------------- | --- | ----- | --------------------------------------------- |
| `schema_version` | `"1"`             | ✓   | BE    | Bump on breaking changes.                     |
| `id`             | string            | ✓   | BE    | e.g. `itn_8f2c…`                              |
| `title`          | string (≤ 80)     | ✓   | LLM   | "Relaxed San Diego Beach Weekend"             |
| `summary`        | string (≤ 300)    |     | LLM   | 1–2 sentence overview for the board header.   |
| `trip`           | [Trip](#trip)     | ✓   | BE    | The parsed request this plan was built from.  |
| `days`           | [Day](#day)[]     | ✓   | LLM   | Length must equal `trip.num_days`.            |
| `tips`           | string[] (≤ 5)    |     | LLM   | Practical notes and assumptions.              |
| `created_at`     | ISO 8601 datetime | ✓   | BE    |                                               |
| `model`          | string            | ✓   | BE    | Model that generated it, for evaluation.      |

## Trip

The preferences used for this plan. The preference-capture stage produces it
from the prompt plus any saved profile, and the backend attaches it, so the
UI can show "planned for: relaxed · mid budget · seafood".

| Field           | Type                                 | Req | Notes                                  |
| --------------- | ------------------------------------ | --- | -------------------------------------- |
| `destination`   | string                               | ✓   | "San Diego, CA"                        |
| `num_days`      | integer (1–14)                       | ✓   |                                        |
| `start_date`    | ISO date                             |     | Omitted when the user gave no dates.   |
| `pace`          | `relaxed` \| `moderate` \| `packed`  | ✓   | How busy each day is (see [Glossary](#glossary)). Default `moderate` if not stated. |
| `activities_per_day` | integer (1–10)                  |     | The user's "things per day" filter. Overrides `pace` for the count. |
| `travelers`     | [Travelers](#travelers)              |     | Who is going. Drives kid-friendly picks, nap gaps, and pacing. |
| `budget`        | `low` \| `mid` \| `high`             |     |                                        |
| `interests`     | string[]                             |     | `["beaches", "seafood"]`               |
| `dietary`       | string[]                             |     | `["vegetarian"]`                       |
| `accessibility` | string[]                             |     | `["wheelchair"]`                       |

### Travelers

| Field        | Type               | Req | Notes                                   |
| ------------ | ------------------ | --- | --------------------------------------- |
| `adults`     | integer (≥ 1)      | ✓   |                                         |
| `child_ages` | integer[] (0–17)   |     | One entry per child. `[1, 3, 4]` = three kids under 5. |

## Day

| Field        | Type                      | Req | Owner | Notes                                         |
| ------------ | ------------------------- | --- | ----- | --------------------------------------------- |
| `id`         | string                    | ✓   | BE    | e.g. `day_1a9e…`                              |
| `day_number` | integer                   | ✓   | LLM   | 1-based and sequential. BE renumbers after a reorder. |
| `date`       | ISO date                  |     | BE    | Derived from `trip.start_date`.               |
| `theme`      | string (≤ 60)             | ✓   | LLM   | "Coastline and tide pools"                    |
| `summary`    | string (≤ 200)            |     | LLM   |                                               |
| `activities` | [Activity](#activity)[]   | ✓   | LLM   | 1–10. Ordered by time.                        |
| `alternatives` | [Activity](#activity)[] |     | LLM   | Activities cut by trimming (or extra options). Can be swapped back in without a new LLM call. |
| `image`      | [Image](#image)           |     | BE + Tool | One hero image per day for the board.     |

## Activity

| Field              | Type                                 | Req | Owner | Notes                                            |
| ------------------ | ------------------------------------ | --- | ----- | ------------------------------------------------ |
| `id`               | string                               | ✓   | BE    | e.g. `act_77b0…`                                 |
| `time_slot`        | `morning` \| `afternoon` \| `evening` | ✓   | LLM   | Always present, so the UI can group by slot.     |
| `start_time`       | `"HH:MM"` (24h)                      |     | LLM   | Optional. Small models handle slots more reliably than exact times. |
| `duration_minutes` | integer (15–720)                     |     | LLM   |                                                  |
| `title`            | string (≤ 80)                        | ✓   | LLM   | "Tide pools at La Jolla Cove"                    |
| `description`      | string (≤ 300)                       | ✓   | LLM   |                                                  |
| `category`         | [Category](#enums)                   | ✓   | LLM   | Drives the card icon and color.                  |
| `rank`             | integer (≥ 1)                        |     | LLM, BE | Importance within the day (1 = top pick). Used for trimming. If missing, BE sets it from list order. Personalization scoring may overwrite it later. |
| `tags`             | [Tag](#enums)[]                      |     | LLM   | Filter chips and badges, e.g. `kid-friendly`.    |
| `location`         | [Location](#location)                | ✓   | LLM + Tool | LLM gives `name`; tools fill the rest.      |
| `cost`             | [Cost](#cost)                        |     | Tool  | Feeds the budget tracker.                        |
| `indoor`           | boolean                              |     | Tool  | For weather-aware swaps.                         |
| `image`            | [Image](#image)                      |     | BE + Tool | Per-activity image, if we choose that (see open questions). |
| `source`           | [Source](#source)                    |     | Tool  | See rule 6 on verified vs. unverified.           |

### Location

| Field      | Type   | Req | Owner | Notes                               |
| ---------- | ------ | --- | ----- | ----------------------------------- |
| `name`     | string | ✓   | LLM   | Place name as the model knows it.   |
| `place_id` | string |     | Tool  | Places API ID. Its presence means "verified". |
| `address`  | string |     | Tool  |                                     |
| `lat`      | number |     | Tool  |                                     |
| `lng`      | number |     | Tool  |                                     |

### Cost

| Field       | Type                                  | Req | Notes                          |
| ----------- | ------------------------------------- | --- | ------------------------------ |
| `level`     | `free` \| `low` \| `mid` \| `high`    | ✓   |                                |
| `estimate`  | number                                |     | Per person.                    |
| `currency`  | ISO 4217 string                       |     | Required if `estimate` is set. |

### Image

| Field    | Type   | Req | Notes                                                       |
| -------- | ------ | --- | ----------------------------------------------------------- |
| `prompt` | string | ✓   | Built by the BE **from validated fields**, never raw user text (safety rule). |
| `url`    | string |     | Empty until the image model returns. UI shows a skeleton until then. |
| `alt`    | string | ✓   | Accessibility text, usually the activity or day title.     |

### Source

| Field        | Type              | Req | Notes |
| ------------ | ----------------- | --- | ----- |
| `url`        | string            | ✓   |       |
| `fetched_at` | ISO 8601 datetime | ✓   |       |

### Enums

`category`: `sightseeing` · `food` · `outdoors` · `excursion` · `culture` ·
`shopping` · `nightlife` · `relaxation` · `transit`

`tags` (starter set, extend as needed): `kid-friendly` · `stroller-ok` ·
`reservation-needed` · `rain-ok` · `wheelchair-accessible` · `vegetarian-options`

## Refinement: trimming a day

When the user sets "things per day" lower than what a day has (e.g. 5 → 3):

1. BE sends the day, `trip`, and the target count to the LLM: *keep the best N
   for these travelers, then re-time them so the day flows.* The LLM can then
   account for nap gaps, travel distance, and meal times.
2. The response has the same Day shape, with **existing activity IDs kept**.
   The kept activities stay in `activities`. The cut ones move to
   `alternatives`.
3. Raising the count again pulls from `alternatives` first (by `rank`) before
   asking the LLM for new ones.

If the LLM call fails, the fallback is to keep the top N by `rank`, with no
re-timing.

## What the LLM actually returns

The model only produces the **LLM-owned** fields. The backend validates them,
then adds IDs, `trip`, and metadata, and tools enrich the result later:

```
LLM output (draft)  →  validate  →  + ids, trip, metadata (BE)  →  + location/cost/images (Tools)  →  UI
```

Minimal valid LLM output:

```json
{
  "title": "Quick Coastal Day",
  "days": [
    {
      "day_number": 1,
      "theme": "Beach morning",
      "activities": [
        {
          "time_slot": "morning",
          "title": "Walk the boardwalk",
          "description": "Easy stroll along the ocean front.",
          "category": "outdoors",
          "location": { "name": "Mission Beach Boardwalk" }
        }
      ]
    }
  ]
}
```

## Validation rules

**Hard (fail → retry once → error):**

- Output parses as JSON and matches the types and enums above.
- `days.length == trip.num_days`, and `day_number` runs 1..N with no gaps.
- Every day has 1–10 activities.
- Activity IDs are unique across `activities` and `alternatives`.
- String length limits hold.

**Soft (logged for evaluation, not rejected):**

- If `activities_per_day` is set, each day has exactly that many activities.
  Otherwise the count fits the pace: relaxed 2–4, moderate 3–5, packed 5–7.
- If `child_ages` includes kids under 5, every activity is tagged
  `kid-friendly`.
- `dietary` restrictions are respected by `food` activities.
- Activities within a day are in time order.

## Complete example (after BE + tools)

A 2-day relaxed trip with the "things per day" filter set to 3. Day 1's first
activity is fully enriched. The rest show the LLM-only state the MVP will
produce. Day 1 also shows a trimmed activity sitting in `alternatives`. All data is illustrative: IDs, URLs,
addresses, and tips are placeholders, not verified facts.

```json
{
  "schema_version": "1",
  "id": "itn_8f2c41",
  "title": "Relaxed San Diego Beach Weekend",
  "summary": "Two slow days of coastline, tide pools, and fresh seafood.",
  "trip": {
    "destination": "San Diego, CA",
    "num_days": 2,
    "start_date": "2026-11-14",
    "pace": "relaxed",
    "activities_per_day": 3,
    "travelers": { "adults": 2, "child_ages": [] },
    "budget": "mid",
    "interests": ["beaches", "seafood"],
    "dietary": [],
    "accessibility": []
  },
  "days": [
    {
      "id": "day_1a9e",
      "day_number": 1,
      "date": "2026-11-14",
      "theme": "Coastline and tide pools",
      "summary": "Ease in with the La Jolla coast and a long seafood dinner.",
      "image": {
        "prompt": "Sunny rocky cove with tide pools and sea lions, La Jolla, travel photo",
        "url": "https://example.com/images/day_1a9e.jpg",
        "alt": "Coastline and tide pools"
      },
      "activities": [
        {
          "id": "act_77b0",
          "time_slot": "morning",
          "start_time": "09:30",
          "duration_minutes": 120,
          "title": "Tide pools at La Jolla Cove",
          "description": "Explore the tide pools at low tide and watch the sea lions on the rocks.",
          "category": "outdoors",
          "rank": 1,
          "tags": ["kid-friendly"],
          "location": {
            "name": "La Jolla Cove",
            "place_id": "example-place-id-123",
            "address": "1100 Coast Blvd, La Jolla, CA 92037",
            "lat": 32.8503,
            "lng": -117.2713
          },
          "cost": { "level": "free" },
          "indoor": false,
          "source": {
            "url": "https://example.com/la-jolla-cove",
            "fetched_at": "2026-11-01T18:00:00Z"
          }
        },
        {
          "id": "act_77b1",
          "time_slot": "afternoon",
          "title": "Lunch and a nap on the beach",
          "description": "Grab fish tacos to go and relax on the sand at La Jolla Shores.",
          "category": "food",
          "rank": 3,
          "location": { "name": "La Jolla Shores" }
        },
        {
          "id": "act_77b2",
          "time_slot": "evening",
          "start_time": "18:30",
          "title": "Seafood dinner by the water",
          "description": "Unhurried dinner with an ocean view at sunset.",
          "category": "food",
          "rank": 2,
          "tags": ["reservation-needed"],
          "location": { "name": "La Jolla Village" }
        }
      ],
      "alternatives": [
        {
          "id": "act_77b3",
          "time_slot": "afternoon",
          "title": "Kayak tour of the sea caves",
          "description": "Guided two-hour paddle along the coast. Cut to keep the day at 3.",
          "category": "excursion",
          "rank": 4,
          "tags": ["reservation-needed"],
          "location": { "name": "La Jolla Shores" }
        }
      ]
    },
    {
      "id": "day_2c31",
      "day_number": 2,
      "date": "2026-11-15",
      "theme": "Bay and old town",
      "activities": [
        {
          "id": "act_91d0",
          "time_slot": "morning",
          "title": "Coronado Beach walk",
          "description": "Flat, wide beach that's perfect for a slow morning walk.",
          "category": "outdoors",
          "rank": 1,
          "location": { "name": "Coronado Beach" }
        },
        {
          "id": "act_91d2",
          "time_slot": "afternoon",
          "title": "Harbor cruise",
          "description": "One-hour narrated boat ride around San Diego Bay.",
          "category": "excursion",
          "rank": 3,
          "tags": ["kid-friendly", "stroller-ok"],
          "location": { "name": "San Diego Bay" }
        },
        {
          "id": "act_91d1",
          "time_slot": "evening",
          "title": "Dinner in Old Town",
          "description": "Casual dinner and a short walk through the historic plaza.",
          "category": "food",
          "rank": 2,
          "location": { "name": "Old Town San Diego" }
        }
      ]
    }
  ],
  "tips": [
    "Check tide times. Tide pools are best at low tide.",
    "Parking near La Jolla Cove fills up by 10am on weekends."
  ],
  "created_at": "2026-11-01T18:00:00Z",
  "model": "Llama-3.1-8B"
}
```

## Open questions (for team review)

1. **Images per day or per activity?** (Also open in PLAN.md.) The schema
   supports both. Per day is cheaper and is the suggested MVP default.
2. **Where does validation live?** Zod in Next.js or Pydantic in FastAPI depends
   on the stack decision. This doc is language-neutral on purpose. Implementing
   validation is a follow-up ticket.
3. **Group trips (feature 10):** does `trip` become `travelers: Trip[]`? That's
   deferred and would be a `schema_version: "2"` change.
4. **Backup options (feature 9):** `day.alternatives` may be enough. Do we
   still need a per-activity `backup`?
5. **Multi-city trips:** `trip.destination` is a single place. Supporting
   "3 days Rome, 2 days Florence" would need an optional `destination` per day.
   Adding it now as optional costs nothing; adding it later is also
   non-breaking.
