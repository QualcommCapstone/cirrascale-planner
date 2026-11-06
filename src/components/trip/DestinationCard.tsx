"use client";

import { cn } from "@/lib/utils";
import type { Destination } from "@/lib/store/itinerary";

interface Props {
  destination: Destination;
  index: number;
  focused: boolean;
  onFocus: (id: string) => void;
}

export function DestinationCard({ destination, index, focused, onFocus }: Props) {
  const { id, name, country, dayStart, dayEnd, summary, activities } = destination;
  const dayLabel = dayStart === dayEnd ? `Day ${dayStart}` : `Days ${dayStart}–${dayEnd}`;

  return (
    <button
      type="button"
      onClick={() => onFocus(id)}
      aria-pressed={focused}
      className={cn(
        "group w-full rounded-lg border bg-card p-3 text-left transition-smooth",
        "hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        focused ? "border-primary/70 ring-1 ring-primary/40" : "border-border"
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-medium transition-smooth",
            focused
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border text-muted-foreground group-hover:border-primary/60"
          )}
        >
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium tracking-tightish">{name}</div>
          {country ? (
            <div className="truncate text-xs text-muted-foreground">{country}</div>
          ) : null}
        </div>
        <span className="shrink-0 rounded-md border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
          {dayLabel}
        </span>
      </div>

      {summary ? (
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{summary}</p>
      ) : null}

      {activities.length > 0 ? (
        <ul className="mt-2 space-y-1">
          {activities.map((a, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-foreground/80">
              <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-primary/70" />
              <span className="min-w-0">{a}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </button>
  );
}
