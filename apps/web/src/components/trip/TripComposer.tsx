"use client";

import { useEffect, useState } from "react";
import { ArrowUp, Loader2, SlidersHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTrip } from "@/lib/store/trip";
import { planTrip } from "@/lib/trip/client";
import { PreferenceChips } from "./PreferenceChips";

/** The prompt box + personalization chips. Compact once a trip is on screen. */
export function TripComposer({ compact = false }: { compact?: boolean }) {
  const storedGoal = useTrip((s) => s.goal);
  const [goal, setGoal] = useState(storedGoal);
  const [showPrefs, setShowPrefs] = useState(!compact);
  const status = useTrip((s) => s.status);
  const preferences = useTrip((s) => s.preferences);
  const setPreferences = useTrip((s) => s.setPreferences);
  const loading = status === "loading";

  // Keep the box in sync when a trip starts elsewhere (sample card, ?q= link).
  useEffect(() => setGoal(storedGoal), [storedGoal]);

  const submit = () => {
    const g = goal.trim();
    if (!g || loading) return;
    void planTrip(g, preferences);
  };

  return (
    <div className="print-hidden space-y-3">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
        className="flex items-center gap-2 rounded-full border border-border bg-card p-1.5 pl-5 shadow-sm transition-smooth focus-within:border-foreground/40 focus-within:shadow-md"
      >
        <input
          type="text"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          maxLength={400}
          placeholder="Where to? e.g. 6 days in Japan for temples and ramen"
          aria-label="Describe a trip"
          className="min-w-0 flex-1 bg-transparent py-2 text-[15px] outline-none placeholder:text-muted-foreground"
        />
        {compact ? (
          <button
            type="button"
            onClick={() => setShowPrefs((v) => !v)}
            aria-expanded={showPrefs}
            aria-label="Preferences"
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-smooth hover:bg-muted hover:text-foreground",
              showPrefs && "bg-muted text-foreground"
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
          </button>
        ) : null}
        <button
          type="submit"
          disabled={loading || !goal.trim()}
          className={cn(
            "inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground transition-smooth",
            "hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          )}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ArrowUp className="h-4 w-4" aria-hidden="true" />}
          {loading ? "Planning" : compact ? "Replan" : "Plan trip"}
        </button>
      </form>

      {showPrefs ? (
        <div className="px-1">
          <PreferenceChips value={preferences} onChange={setPreferences} disabled={loading} />
        </div>
      ) : null}
    </div>
  );
}
