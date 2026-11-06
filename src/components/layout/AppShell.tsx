"use client";

import { useState } from "react";
import { NavRail } from "./NavRail";
import { Header } from "./Header";
import { ItineraryPanel } from "@/components/trip/ItineraryPanel";
import GlobeClient from "@/components/globe/GlobeClient";
import { cn } from "@/lib/utils";
import { Globe2, ListChecks } from "lucide-react";

type MobileTab = "globe" | "itinerary";

export function AppShell() {
  const [tab, setTab] = useState<MobileTab>("itinerary");

  return (
    <div className="flex h-[100dvh] overflow-hidden bg-background text-foreground">
      <NavRail />

      <div className="flex min-w-0 flex-1 flex-col">
        <Header />

        {/* Desktop: globe + fixed side panel. Mobile: one pane via tabs. */}
        <main className="relative flex min-h-0 flex-1">
          {/* Globe */}
          <section
            aria-label="Trip map"
            className={cn(
              "relative min-w-0 flex-1 bg-background",
              tab === "globe" ? "block" : "hidden md:block"
            )}
          >
            <GlobeClient />
          </section>

          {/* Itinerary */}
          <aside
            aria-label="Itinerary"
            className={cn(
              "w-full border-l border-border bg-background md:w-[380px] md:shrink-0",
              tab === "itinerary" ? "block" : "hidden md:block"
            )}
          >
            <ItineraryPanel />
          </aside>

          {/* Mobile tab switch */}
          <div className="absolute inset-x-0 bottom-3 flex justify-center md:hidden">
            <div className="flex items-center gap-1 rounded-full border border-border bg-card p-1 shadow-lg">
              <TabButton active={tab === "globe"} onClick={() => setTab("globe")}>
                <Globe2 className="h-3.5 w-3.5" /> Map
              </TabButton>
              <TabButton active={tab === "itinerary"} onClick={() => setTab("itinerary")}>
                <ListChecks className="h-3.5 w-3.5" /> Itinerary
              </TabButton>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

function TabButton({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-smooth",
        active ? "bg-primary text-primary-foreground" : "text-muted-foreground"
      )}
    >
      {children}
    </button>
  );
}
