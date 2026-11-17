"use client";

import { Check, Cpu, Sparkle } from "lucide-react";
import { useTrip } from "@/lib/store/trip";
import type { Trip } from "@/lib/trip/types";
import { Photo } from "./Photo";

export function TripOverview({ trip }: { trip: Trip }) {
  const generationMs = useTrip((s) => s.generationMs);
  const status = useTrip((s) => s.status);
  const focusStop = useTrip((s) => s.focusStop);
  const prefs = trip.preferences;
  const planned = [...prefs.interests, `${prefs.budget} budget`, `${prefs.pace} pace`];

  return (
    <header className="animate-rise-in">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        <Sparkle className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
        Trip overview
      </p>

      <h1 className="mt-3 text-3xl font-bold leading-[1.08] tracking-display text-balance sm:text-4xl">
        {trip.title}
        {trip.where && !trip.title.toLowerCase().includes(trip.where.toLowerCase()) ? (
          <span className="text-muted-foreground/70"> — {trip.where}</span>
        ) : null}
      </h1>

      {trip.summary ? (
        <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">{trip.summary}</p>
      ) : null}

      {trip.vibes.length > 0 ? (
        <ul className="mt-4 flex flex-wrap gap-x-4 gap-y-2" aria-label="Trip vibes">
          {trip.vibes.map((v) => (
            <li key={v} className="inline-flex items-center gap-1.5 text-sm font-medium">
              <Check className="h-3.5 w-3.5 text-brand" aria-hidden="true" />
              {v}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        {/* Facts */}
        <dl className="min-w-0 divide-y divide-border border-y border-border text-sm">
          <Fact label="Where" value={trip.where || trip.stops.map((s) => s.city).join(", ")} />
          <Fact label="When" value={trip.when || "Any time"} />
          <Fact label="Days" value={`${trip.days} day${trip.days === 1 ? "" : "s"}`} />
          <Fact label="Route" value={trip.stops.map((s) => s.city).join(" → ")} />
        </dl>

        {/* Stop photo strip */}
        <ol className="no-scrollbar flex min-w-0 snap-x gap-3 overflow-x-auto" aria-label="Stops">
          {trip.stops.map((s, i) => (
            <li key={s.id} className="w-[46%] min-w-[150px] shrink-0 snap-start">
              <button
                type="button"
                onClick={() => focusStop(s.id, "globe")}
                className="group relative block aspect-[3/4] w-full overflow-hidden rounded-xl bg-muted text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={`Go to stop ${i + 1}, ${s.city}`}
              >
                <Photo photo={s.photo} alt={s.city} className="transition-transform duration-500 group-hover:scale-105" />
                <span className="photo-scrim absolute inset-0" />
                <span className="absolute left-2.5 top-2.5 flex h-6 w-6 items-center justify-center rounded-full bg-background text-[11px] font-bold">
                  {i + 1}
                </span>
                <span className="absolute inset-x-0 bottom-0 p-3 text-white">
                  <span className="block text-base font-bold leading-tight">{s.city}</span>
                  {s.headline ? <span className="block text-xs text-white/80">{s.headline}</span> : null}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Planned for</span>
        {planned.map((p) => (
          <span key={p} className="rounded-full border border-border bg-card px-2.5 py-1 font-medium">
            {p}
          </span>
        ))}
        {status === "ready" && generationMs ? (
          <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
            <Cpu className="h-3 w-3" aria-hidden="true" />
            Generated in {(generationMs / 1000).toFixed(1)}s on Qualcomm Cloud AI 100
          </span>
        ) : null}
      </div>
    </header>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-semibold">{value}</dd>
    </div>
  );
}
