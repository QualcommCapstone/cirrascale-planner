"use client";

import { useEffect } from "react";
import { Header } from "./Header";
import { TripStory } from "@/components/trip/TripStory";
import GlobeClient from "@/components/globe/GlobeClient";
import { useTrip } from "@/lib/store/trip";
import { cancelPlanning, planTrip } from "@/lib/trip/client";
import { decodeTrip } from "@/lib/trip/share";

/**
 * /planner layout. Desktop: the globe stays put on the left while the trip
 * scrolls as a story on the right. Mobile: a short globe strip on top, story
 * below. Opens a shared trip from #trip=… or starts one from ?q=… (landing).
 */
export function AppShell() {
  useEffect(() => {
    let cancelled = false;

    const openSharedTrip = async () => {
      const shared = await decodeTrip(window.location.hash);
      if (!cancelled && shared) {
        cancelPlanning();
        useTrip.getState().loadTrip(shared);
      }
      return shared;
    };

    (async () => {
      if (await openSharedTrip()) return;
      const q = new URLSearchParams(window.location.search).get("q")?.trim();
      if (!cancelled && q && useTrip.getState().status === "idle") {
        window.history.replaceState(null, "", "/planner");
        void planTrip(q.slice(0, 400), useTrip.getState().preferences);
      }
    })();

    // A share link opened while already on /planner only changes the hash.
    const onHash = () => void openSharedTrip();
    window.addEventListener("hashchange", onHash);
    return () => {
      cancelled = true;
      window.removeEventListener("hashchange", onHash);
    };
  }, []);

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-background text-foreground print:block print:h-auto print:overflow-visible">
      <Header />
      <main className="flex min-h-0 flex-1 flex-col md:flex-row print:block">
        <section
          aria-label="Trip map"
          className="print-hidden relative h-[34vh] shrink-0 border-b border-border bg-muted/40 md:h-auto md:w-[44%] md:border-b-0 md:border-r lg:w-[42%]"
        >
          <GlobeClient />
        </section>
        <section aria-label="Itinerary" className="print-full min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden">
          <TripStory />
        </section>
      </main>
    </div>
  );
}
