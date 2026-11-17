"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, Globe2, Link2, Plus, Printer } from "lucide-react";
import { useTrip } from "@/lib/store/trip";
import { cancelPlanning } from "@/lib/trip/client";
import { encodeTrip } from "@/lib/trip/share";
import ModeToggle from "@/app/components/ModeToggle";

export function Header() {
  const trip = useTrip((s) => s.trip);
  const status = useTrip((s) => s.status);
  const reset = useTrip((s) => s.reset);
  const [copied, setCopied] = useState(false);
  const ready = status === "ready" && trip;

  const share = async () => {
    if (!trip) return;
    const hash = await encodeTrip(trip);
    const url = `${window.location.origin}/planner#${hash}`;
    window.history.replaceState(null, "", `/planner#${hash}`);
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Copy this link to share the trip:", url);
    }
  };

  const newTrip = () => {
    cancelPlanning();
    reset();
    window.history.replaceState(null, "", "/planner");
  };

  return (
    <header className="print-hidden flex h-14 shrink-0 items-center justify-between gap-3 border-b border-border bg-background/90 px-4 backdrop-blur sm:px-5">
      <div className="flex min-w-0 items-center gap-2.5">
        <Link href="/" className="flex shrink-0 items-center gap-2 font-display text-[15px] font-bold tracking-tight">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-background">
            <Globe2 className="h-4 w-4" aria-hidden="true" />
          </span>
          Cirrascale Planner
        </Link>
        {trip ? (
          <>
            <span className="hidden text-muted-foreground/50 sm:inline">/</span>
            <span className="hidden truncate text-sm text-muted-foreground sm:inline">{trip.title}</span>
          </>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {trip || status === "loading" ? (
          <HeaderButton onClick={newTrip} label="New trip">
            <Plus className="h-4 w-4" />
          </HeaderButton>
        ) : null}
        {ready ? (
          <>
            <HeaderButton onClick={() => void share()} label={copied ? "Link copied" : "Share"}>
              {copied ? <Check className="h-4 w-4" /> : <Link2 className="h-4 w-4" />}
            </HeaderButton>
            <HeaderButton onClick={() => window.print()} label="Save PDF">
              <Printer className="h-4 w-4" />
            </HeaderButton>
          </>
        ) : null}
        <ModeToggle />
      </div>
    </header>
  );
}

function HeaderButton({ children, label, onClick }: { children: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-9 items-center gap-1.5 rounded-full px-3 text-sm font-medium text-muted-foreground transition-smooth hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {children}
      <span className="hidden md:inline">{label}</span>
      <span className="sr-only md:hidden">{label}</span>
    </button>
  );
}
