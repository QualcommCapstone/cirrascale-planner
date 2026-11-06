"use client";

import { useState } from "react";
import { ArrowUp, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useItinerary, type Trip } from "@/lib/store/itinerary";

const SUGGESTIONS = [
  "10-day trip through Japan",
  "A week in Italy: Rome, Florence, Venice",
  "Southeast Asia backpacking, 2 weeks",
];

export function TripComposer() {
  const [goal, setGoal] = useState("");
  const status = useItinerary((s) => s.status);
  const setStatus = useItinerary((s) => s.setStatus);
  const setTrip = useItinerary((s) => s.setTrip);
  const loading = status === "loading";

  const submit = async (value: string) => {
    const g = value.trim();
    if (!g || loading) return;
    setStatus("loading");
    try {
      const res = await fetch("/api/itinerary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: g }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus("error", data.error ?? "Could not build an itinerary.");
        return;
      }
      setTrip(data as Trip);
    } catch {
      setStatus("error", "Network error contacting the planner.");
    }
  };

  return (
    <div className="space-y-2">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void submit(goal);
        }}
        className="flex items-center gap-2 rounded-lg border border-border bg-card p-1.5 transition-smooth focus-within:border-primary/60"
      >
        <input
          type="text"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Describe a trip…"
          aria-label="Describe a trip"
          className="min-w-0 flex-1 bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          disabled={loading || !goal.trim()}
          aria-label="Generate itinerary"
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition-smooth",
            "bg-primary text-primary-foreground hover:opacity-90",
            "disabled:opacity-40 disabled:cursor-not-allowed"
          )}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ArrowUp className="h-4 w-4" />
          )}
        </button>
      </form>

      <div className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            disabled={loading}
            onClick={() => {
              setGoal(s);
              void submit(s);
            }}
            className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-smooth hover:border-primary/50 hover:text-foreground disabled:opacity-40"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
