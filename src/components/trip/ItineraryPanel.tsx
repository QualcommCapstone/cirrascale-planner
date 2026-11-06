"use client";

import { useItinerary } from "@/lib/store/itinerary";
import { TripComposer } from "./TripComposer";
import { DestinationCard } from "./DestinationCard";
import { AiItinerary } from "./AiItinerary";
import { AlertCircle, Compass, Loader2 } from "lucide-react";

export function ItineraryPanel() {
  const status = useItinerary((s) => s.status);
  const error = useItinerary((s) => s.error);
  const title = useItinerary((s) => s.title);
  const destinations = useItinerary((s) => s.destinations);
  const focusedId = useItinerary((s) => s.focusedId);
  const focus = useItinerary((s) => s.focus);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <TripComposer />
      </div>

      <div className="flex-1 overflow-y-auto">
        {status === "idle" && (
          <EmptyState />
        )}

        {status === "loading" && (
          <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            Charting your route…
          </div>
        )}

        {status === "error" && (
          <div className="m-3 flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-foreground">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span>{error ?? "Something went wrong."}</span>
          </div>
        )}

        {status === "ready" && destinations.length > 0 && (
          <div className="space-y-3 p-3">
            {title ? (
              <h2 className="px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {title}
              </h2>
            ) : null}

            <ol className="space-y-2">
              {destinations.map((d, i) => (
                <li key={d.id}>
                  <DestinationCard
                    destination={d}
                    index={i}
                    focused={d.id === focusedId}
                    onFocus={focus}
                  />
                </li>
              ))}
            </ol>

            <AiItinerary />
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-border">
        <Compass className="h-5 w-5 text-primary" />
      </div>
      <div>
        <p className="text-sm font-medium tracking-tightish">Plan a trip</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Describe where you want to go and we&apos;ll map a route across the globe.
        </p>
      </div>
    </div>
  );
}
