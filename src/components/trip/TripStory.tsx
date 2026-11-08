"use client";

import { Fragment } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { useTrip } from "@/lib/store/trip";
import { planTrip } from "@/lib/trip/client";
import { TripComposer } from "./TripComposer";
import { TripOverview } from "./TripOverview";
import { StopSection } from "./StopSection";
import { TransitConnector } from "./TransitConnector";
import { SampleTrips } from "./SampleTrips";

/** The scrolling side of /planner: welcome → progress → the trip as a story. */
export function TripStory() {
  const trip = useTrip((s) => s.trip);
  const status = useTrip((s) => s.status);
  const error = useTrip((s) => s.error);
  const pending = useTrip((s) => s.pendingStopIds);
  const failed = useTrip((s) => s.failedStopIds);
  const preferences = useTrip((s) => s.preferences);

  if (!trip && status !== "loading") {
    return (
      <div className="mx-auto max-w-3xl px-5 py-10 sm:px-8 sm:py-14">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Plan a trip</p>
        <h1 className="mt-3 text-4xl font-bold leading-[1.05] tracking-display text-balance sm:text-5xl">
          Where to next?
        </h1>
        <p className="mt-3 max-w-xl text-base leading-relaxed text-muted-foreground">
          Describe a trip in a sentence. You&apos;ll get real places with photos, a day-by-day plan and the
          route on the globe.
        </p>
        <div className="mt-7">
          <TripComposer />
        </div>
        {status === "error" && error ? <ErrorNote message={error} /> : null}
        <h2 className="mb-3 mt-12 text-sm font-semibold text-muted-foreground">Or start from one of these</h2>
        <SampleTrips onPick={(d) => void planTrip(d.prompt, preferences)} />
      </div>
    );
  }

  return (
    <div className="print-full mx-auto max-w-4xl px-5 pb-16 pt-5 sm:px-8">
      <TripComposer compact />

      {status === "error" && error ? <ErrorNote message={error} /> : null}

      {!trip ? (
        <Progress />
      ) : (
        <div className="mt-8">
          <TripOverview trip={trip} />
          {status === "loading" && pending.length > 0 ? (
            <p className="mt-6 flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
              <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />
              Planning days for {trip.stops.filter((s) => pending.includes(s.id)).map((s) => s.city).join(", ")}…
            </p>
          ) : null}

          <div className="mt-10">
            {trip.stops.map((stop, i) => {
              const leg = trip.legs.find((l) => l.fromId === trip.stops[i - 1]?.id && l.toId === stop.id);
              return (
                <Fragment key={stop.id}>
                  {leg ? <TransitConnector leg={leg} from={trip.stops[i - 1].city} to={stop.city} /> : null}
                  <StopSection
                    stop={stop}
                    number={i + 1}
                    pending={pending.includes(stop.id)}
                    failed={failed.includes(stop.id)}
                  />
                </Fragment>
              );
            })}
          </div>

          <footer className="mt-14 border-t border-border pt-5 text-xs leading-relaxed text-muted-foreground">
            Places marked <span className="font-medium text-foreground">Not verified</span> couldn&apos;t be
            matched on Wikipedia and aren&apos;t pinned on the map, so check them before you go. Photos are
            free-licensed images from Wikimedia Commons; tap a photo&apos;s credit for its author and license.
          </footer>
        </div>
      )}
    </div>
  );
}

function Progress() {
  return (
    <div className="mt-10 rounded-xl border border-border bg-card p-6" aria-live="polite">
      <div className="flex items-center gap-2 text-sm font-semibold">
        <Loader2 className="h-4 w-4 animate-spin text-brand" aria-hidden="true" />
        Sketching your route…
      </div>
      <ol className="mt-4 space-y-2 text-sm text-muted-foreground">
        <li>1. Choosing stops, where to stay and what to eat</li>
        <li>2. Planning each day, morning to evening</li>
        <li>3. Checking every place against Wikipedia and finding photos</li>
      </ol>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <div className="aspect-[16/9] animate-pulse rounded-xl bg-muted sm:col-span-2" />
        <div className="h-20 animate-pulse rounded-xl bg-muted" />
        <div className="h-20 animate-pulse rounded-xl bg-muted" />
      </div>
    </div>
  );
}

function ErrorNote({ message }: { message: string }) {
  return (
    <div className="mt-5 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm" role="alert">
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
