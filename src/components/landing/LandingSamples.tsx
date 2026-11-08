"use client";

import { useRouter } from "next/navigation";
import { SampleTrips } from "@/components/trip/SampleTrips";

/** Sample trips on the landing page: open the planner with that prompt. */
export function LandingSamples() {
  const router = useRouter();
  return (
    <SampleTrips onPick={(d) => router.push(`/planner?q=${encodeURIComponent(d.prompt)}`)} />
  );
}
