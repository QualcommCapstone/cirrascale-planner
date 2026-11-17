import { create } from "zustand";
import {
  DEFAULT_PREFERENCES,
  type Activity,
  type Day,
  type FoodPick,
  type Preferences,
  type Stop,
  type Trip,
} from "@/lib/trip/types";

export type TripStatus = "idle" | "loading" | "ready" | "error";

/** Where a focus change came from: the globe scrolls the story, the story flies the globe. */
export type FocusSource = "story" | "globe";

interface TripState {
  trip: Trip | null;
  status: TripStatus;
  error: string | null;
  /** The prompt that produced the current trip. */
  goal: string;
  preferences: Preferences;
  /** Stops whose day plan is still being generated / failed. */
  pendingStopIds: string[];
  failedStopIds: string[];
  /** Wall-clock generation time reported by the server. */
  generationMs: number | null;

  focusedStopId: string | null;
  focusedActivityId: string | null;
  hoveredActivityId: string | null;
  focusSource: FocusSource;
  /** Bumps on every focus so re-focusing the same item still scrolls/flies. */
  focusTick: number;

  setPreferences: (p: Preferences) => void;
  start: (goal: string) => void;
  setOutline: (trip: Trip) => void;
  setStopDays: (stopId: string, days: Day[], food: FoodPick[]) => void;
  stopFailed: (stopId: string) => void;
  finish: (ms: number) => void;
  fail: (message: string) => void;
  /** Load a complete trip (e.g. from a share link). */
  loadTrip: (trip: Trip) => void;

  focusStop: (id: string | null, source?: FocusSource) => void;
  focusActivity: (id: string | null, source?: FocusSource) => void;
  hoverActivity: (id: string | null) => void;
  reset: () => void;
}

const EMPTY = {
  trip: null,
  status: "idle" as TripStatus,
  error: null,
  goal: "",
  pendingStopIds: [],
  failedStopIds: [],
  generationMs: null,
  focusedStopId: null,
  focusedActivityId: null,
  hoveredActivityId: null,
  focusSource: "story" as FocusSource,
  focusTick: 0,
};

export const useTrip = create<TripState>((set) => ({
  ...EMPTY,
  preferences: DEFAULT_PREFERENCES,

  setPreferences: (preferences) => set({ preferences }),

  start: (goal) => set((s) => ({ ...EMPTY, preferences: s.preferences, goal, status: "loading" })),

  setOutline: (trip) =>
    set({
      trip,
      pendingStopIds: trip.stops.map((st) => st.id),
      focusedStopId: null,
    }),

  setStopDays: (stopId, days, food) =>
    set((s) => {
      if (!s.trip) return {};
      return {
        trip: {
          ...s.trip,
          stops: s.trip.stops.map((st) => (st.id === stopId ? { ...st, days, food } : st)),
        },
        pendingStopIds: s.pendingStopIds.filter((id) => id !== stopId),
      };
    }),

  stopFailed: (stopId) =>
    set((s) => ({
      pendingStopIds: s.pendingStopIds.filter((id) => id !== stopId),
      failedStopIds: [...s.failedStopIds, stopId],
    })),

  finish: (generationMs) =>
    set((s) => ({ status: s.trip ? "ready" : "error", generationMs, pendingStopIds: [] })),

  fail: (error) => set({ status: "error", error, pendingStopIds: [] }),

  loadTrip: (trip) =>
    set((s) => ({
      ...EMPTY,
      trip,
      preferences: trip.preferences ?? s.preferences,
      status: "ready",
    })),

  focusStop: (id, source = "story") =>
    set((s) => ({
      focusedStopId: id,
      focusedActivityId: null,
      focusSource: source,
      focusTick: s.focusTick + 1,
    })),

  focusActivity: (id, source = "story") =>
    set((s) => ({
      focusedActivityId: id,
      focusedStopId: id ? stopOf(s.trip, id)?.id ?? s.focusedStopId : s.focusedStopId,
      focusSource: source,
      focusTick: s.focusTick + 1,
    })),

  hoverActivity: (hoveredActivityId) => set({ hoveredActivityId }),

  reset: () => set((s) => ({ ...EMPTY, preferences: s.preferences })),
}));

// --- Selectors -------------------------------------------------------------

export function stopOf(trip: Trip | null, activityId: string): Stop | undefined {
  return trip?.stops.find((s) => s.days.some((d) => d.activities.some((a) => a.id === activityId)));
}

export function allActivities(trip: Trip | null): (Activity & { stopId: string })[] {
  if (!trip) return [];
  return trip.stops.flatMap((s) =>
    s.days.flatMap((d) => d.activities.map((a) => ({ ...a, stopId: s.id })))
  );
}

/** Activities with real coordinates, numbered in trip order within their stop. */
export function pinnedActivities(trip: Trip | null) {
  return allActivities(trip).filter(
    (a): a is typeof a & { lat: number; lng: number } => a.lat !== null && a.lng !== null
  );
}
