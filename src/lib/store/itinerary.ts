import { create } from "zustand";

export interface Destination {
  id: string;
  name: string;
  country: string;
  lat: number;
  lng: number;
  dayStart: number;
  dayEnd: number;
  summary: string;
  activities: string[];
}

export interface Trip {
  title: string;
  destinations: Destination[];
}

export type TripStatus = "idle" | "loading" | "ready" | "error";

/** An arc between two consecutive stops, for the globe's route lines. */
export interface RouteArc {
  startLat: number;
  startLng: number;
  endLat: number;
  endLng: number;
  fromId: string;
  toId: string;
}

interface ItineraryState {
  title: string;
  destinations: Destination[];
  focusedId: string | null;
  status: TripStatus;
  error: string | null;

  setStatus: (status: TripStatus, error?: string | null) => void;
  setTrip: (trip: Trip) => void;
  focus: (id: string | null) => void;
  reset: () => void;
}

export const useItinerary = create<ItineraryState>((set) => ({
  title: "",
  destinations: [],
  focusedId: null,
  status: "idle",
  error: null,

  setStatus: (status, error = null) => set({ status, error }),
  setTrip: (trip) =>
    set({
      title: trip.title,
      destinations: trip.destinations,
      focusedId: trip.destinations[0]?.id ?? null,
      status: "ready",
      error: null,
    }),
  focus: (id) => set({ focusedId: id }),
  reset: () =>
    set({ title: "", destinations: [], focusedId: null, status: "idle", error: null }),
}));

/** Route arcs between consecutive destinations (itinerary order). */
export function selectArcs(destinations: Destination[]): RouteArc[] {
  const arcs: RouteArc[] = [];
  for (let i = 0; i < destinations.length - 1; i++) {
    const a = destinations[i];
    const b = destinations[i + 1];
    arcs.push({
      startLat: a.lat,
      startLng: a.lng,
      endLat: b.lat,
      endLng: b.lng,
      fromId: a.id,
      toId: b.id,
    });
  }
  return arcs;
}

export function selectFocused(state: ItineraryState): Destination | null {
  return state.destinations.find((d) => d.id === state.focusedId) ?? null;
}
