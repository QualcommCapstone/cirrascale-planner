/** Display helpers for trip data (pure, unit-tested). */
import type { Category, Cost, Mode, Slot } from "./types";

/** "Day 3" or "Days 3–5". */
export function formatDays(dayStart: number, dayEnd: number): string {
  return dayStart === dayEnd ? `Day ${dayStart}` : `Days ${dayStart}–${dayEnd}`;
}

/** 45 -> "45m", 120 -> "2h", 135 -> "2h 15m". */
export function formatDuration(mins: number): string {
  const m = Math.max(0, Math.round(mins));
  const h = Math.floor(m / 60);
  const r = m % 60;
  if (h === 0) return `${r}m`;
  return r === 0 ? `${h}h` : `${h}h ${r}m`;
}

export const SLOT_LABEL: Record<Slot, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
};

export const CATEGORY_LABEL: Record<Category, string> = {
  sight: "Sight",
  food: "Food",
  nature: "Nature",
  culture: "Culture",
  nightlife: "Nightlife",
  shopping: "Shopping",
};

export const COST_LABEL: Record<Cost, string> = {
  free: "Free",
  $: "$",
  $$: "$$",
  $$$: "$$$",
};

export const MODE_LABEL: Record<Mode, string> = {
  train: "train",
  flight: "flight",
  bus: "bus",
  car: "drive",
  ferry: "ferry",
};

/** Only https URLs reach href/src (shared trips are untrusted input). */
export function safeUrl(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url).protocol === "https:" ? url : undefined;
  } catch {
    return undefined;
  }
}
