import { Bus, Car, Plane, Ship, TrainFront } from "lucide-react";
import { MODE_LABEL, formatDuration } from "@/lib/trip/format";
import type { Leg, Mode } from "@/lib/trip/types";

const ICON: Record<Mode, typeof TrainFront> = {
  train: TrainFront,
  flight: Plane,
  bus: Bus,
  car: Car,
  ferry: Ship,
};

/** "Tokyo → Kyoto · 2h 15m train", drawn as a dashed connector between stop sections. */
export function TransitConnector({ leg, from, to }: { leg: Leg; from: string; to: string }) {
  const Icon = ICON[leg.mode];
  return (
    <div className="print-avoid-break flex items-stretch gap-4 py-2 pl-3" role="note" aria-label={`Travel from ${from} to ${to}`}>
      <div className="flex w-6 flex-col items-center">
        <span className="w-px flex-1 border-l-2 border-dashed border-brand/50" />
        <span className="my-1 flex h-7 w-7 items-center justify-center rounded-full bg-brand text-brand-foreground">
          <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
        <span className="w-px flex-1 border-l-2 border-dashed border-brand/50" />
      </div>
      <div className="py-3">
        <p className="text-sm font-semibold">
          {from} <span className="text-muted-foreground">→</span> {to}
          <span className="font-normal text-muted-foreground">
            {" · "}
            {leg.estimated ? "≈ " : ""}
            {formatDuration(leg.durationMins)} {MODE_LABEL[leg.mode]}
          </span>
        </p>
        {leg.notes ? <p className="mt-0.5 text-xs text-muted-foreground">{leg.notes}</p> : null}
        {leg.estimated ? (
          <p className="mt-0.5 text-[11px] text-muted-foreground/80">Time estimated from distance.</p>
        ) : null}
      </div>
    </div>
  );
}
