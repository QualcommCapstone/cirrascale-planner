/**
 * Trip data model shared by the server (generation) and the client (UI, globe).
 *
 * The model's raw output is parsed leniently in normalize.ts and turned into
 * these types; nothing reaches the UI without passing through there.
 */
import { z } from "zod";

// --- Personalization -------------------------------------------------------

export const INTERESTS = ["Food", "Nature", "Culture", "Nightlife"] as const;
export const BUDGETS = ["Budget", "Mid", "Luxury"] as const;
export const PACES = ["Relaxed", "Balanced", "Packed"] as const;

export const PreferencesSchema = z.object({
  interests: z.array(z.enum(INTERESTS)).max(INTERESTS.length).default([]),
  budget: z.enum(BUDGETS).default("Mid"),
  pace: z.enum(PACES).default("Balanced"),
});
export type Preferences = z.infer<typeof PreferencesSchema>;

export const DEFAULT_PREFERENCES: Preferences = {
  interests: [],
  budget: "Mid",
  pace: "Balanced",
};

/** Body of POST /api/itinerary. Length limits keep it from being a free-form prompt proxy. */
export const TripRequestSchema = z.object({
  goal: z.string().trim().min(1).max(400),
  preferences: PreferencesSchema.default(DEFAULT_PREFERENCES),
});
export type TripRequest = z.infer<typeof TripRequestSchema>;

// --- Enums -----------------------------------------------------------------

export const SLOTS = ["morning", "afternoon", "evening"] as const;
export type Slot = (typeof SLOTS)[number];

export const CATEGORIES = ["sight", "food", "nature", "culture", "nightlife", "shopping"] as const;
export type Category = (typeof CATEGORIES)[number];

export const COSTS = ["free", "$", "$$", "$$$"] as const;
export type Cost = (typeof COSTS)[number];

export const MODES = ["train", "flight", "bus", "car", "ferry"] as const;
export type Mode = (typeof MODES)[number];

// --- Trip ------------------------------------------------------------------

export interface Photo {
  url: string;
  /** Page with the image's license and author (Wikimedia Commons file page). */
  creditUrl: string;
  /** What the photo shows: the place itself, its neighborhood, or the city. */
  kind: "place" | "area" | "city";
}

export interface Activity {
  id: string;
  slot: Slot;
  name: string;
  neighborhood: string;
  durationMins: number;
  cost: Cost;
  category: Category;
  reason: string;
  /** Real coordinates when verified against Wikipedia, otherwise null (no globe pin). */
  lat: number | null;
  lng: number | null;
  verified: boolean;
  photo: Photo | null;
  /** Wikipedia article the place was verified against. */
  sourceUrl: string | null;
}

export interface Day {
  day: number;
  activities: Activity[];
}

export interface FoodPick {
  name: string;
  note: string;
}

export interface Stop {
  id: string;
  city: string;
  country: string;
  lat: number;
  lng: number;
  dayStart: number;
  dayEnd: number;
  headline: string;
  intro: string;
  stay: { area: string; why: string };
  food: FoodPick[];
  photo: Photo | null;
  /** Empty until the stop's day plan has been generated. */
  days: Day[];
}

export interface Leg {
  fromId: string;
  toId: string;
  mode: Mode;
  durationMins: number;
  notes: string;
  /** True when the model's duration was implausible and we estimated from distance. */
  estimated: boolean;
}

export interface Trip {
  title: string;
  summary: string;
  where: string;
  when: string;
  days: number;
  vibes: string[];
  preferences: Preferences;
  stops: Stop[];
  legs: Leg[];
}

// --- Streaming -------------------------------------------------------------

/** One NDJSON line from POST /api/itinerary. */
export type TripEvent =
  | { type: "outline"; trip: Trip }
  /** `food` drops picks that became a planned activity, so nothing shows twice. */
  | { type: "stop"; stopId: string; days: Day[]; food: FoodPick[] }
  | { type: "stopError"; stopId: string }
  | { type: "done"; ms: number }
  | { type: "error"; message: string };
