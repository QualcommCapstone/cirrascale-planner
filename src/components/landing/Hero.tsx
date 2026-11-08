"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUp, Cpu, Globe2, MapPinned, Timer } from "lucide-react";
import { cn } from "@/lib/utils";
import { DESTINATIONS, destinationPhoto } from "@/lib/destinations";
import { lastGenerationTime } from "@/lib/trip/client";
import { usePrefersReducedMotion } from "@/lib/use-reduced-motion";
import ModeToggle from "@/app/components/ModeToggle";

const ROTATE_MS = 6500;

/** Full-bleed rotating destination photo; the prompt box is the call to action. */
export function Hero() {
  const router = useRouter();
  const reducedMotion = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [goal, setGoal] = useState("");
  const [typing, setTyping] = useState(false);
  const [lastMs, setLastMs] = useState<number | null>(null);
  const current = DESTINATIONS[index];

  useEffect(() => setLastMs(lastGenerationTime()), []);

  // Rotate photos, but hold still while the visitor is typing.
  useEffect(() => {
    if (reducedMotion || typing) return;
    const t = setInterval(() => setIndex((i) => (i + 1) % DESTINATIONS.length), ROTATE_MS);
    return () => clearInterval(t);
  }, [reducedMotion, typing]);

  const submit = () => {
    const q = (goal.trim() || current.prompt).slice(0, 400);
    router.push(`/planner?q=${encodeURIComponent(q)}`);
  };

  return (
    <section className="relative px-3 pt-3 sm:px-4 sm:pt-4">
      <div className="relative isolate flex min-h-[640px] flex-col overflow-hidden rounded-[28px] bg-neutral-900 text-white h-[calc(100dvh-1.5rem)] sm:h-[calc(100dvh-2rem)]">
        {/* Photos (cross-fade) */}
        {DESTINATIONS.map((d, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={d.place}
            src={destinationPhoto(d, 1920)}
            alt={i === index ? `${d.place}, ${d.region}` : ""}
            aria-hidden={i !== index}
            loading={i === 0 ? "eager" : "lazy"}
            referrerPolicy="no-referrer"
            className={cn(
              "absolute inset-0 -z-10 h-full w-full object-cover transition-opacity [transition-duration:1400ms] ease-out",
              i === index ? "opacity-100" : "opacity-0"
            )}
          />
        ))}
        <div className="absolute inset-0 -z-10 bg-gradient-to-t from-black/75 via-black/20 to-black/35" />

        {/* Nav */}
        <nav className="flex items-center justify-between px-5 py-4 sm:px-8 sm:py-6">
          <Link href="/" className="flex items-center gap-2 font-display text-base font-bold tracking-tight">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-neutral-900">
              <Globe2 className="h-4 w-4" aria-hidden="true" />
            </span>
            Cirrascale Planner
          </Link>
          <div className="flex items-center gap-1 rounded-full bg-white/15 p-1 backdrop-blur-md">
            <Link href="/planner" className="rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-neutral-900 transition-smooth hover:bg-white/90">
              Open planner
            </Link>
            <span className="text-white [&_button]:text-white/80 [&_button:hover]:text-white">
              <ModeToggle />
            </span>
          </div>
        </nav>

        {/* Headline + prompt */}
        <div className="mt-auto px-5 pb-6 sm:px-10 sm:pb-10">
          <p className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-xs font-medium backdrop-blur-md">
            <MapPinned className="h-3.5 w-3.5" aria-hidden="true" />
            {current.place} · {current.region}
          </p>
          <h1 className="max-w-4xl font-display text-[clamp(2.6rem,7vw,6rem)] font-extrabold uppercase leading-[0.92] tracking-[-0.025em] text-balance">
            Say where.
            <br />
            <span className="text-white/80">See the trip.</span>
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-white/85 sm:text-lg">
            One sentence in. Real places with photos, a day-by-day plan and your route on a globe out.
          </p>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
            className="mt-6 flex max-w-2xl items-center gap-2 rounded-full bg-white p-1.5 pl-5 text-neutral-900 shadow-2xl"
          >
            <input
              type="text"
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              onFocus={() => setTyping(true)}
              onBlur={() => setTyping(goal.trim().length > 0)}
              maxLength={400}
              placeholder={current.prompt}
              aria-label="Describe a trip"
              className="min-w-0 flex-1 bg-transparent py-2.5 text-[15px] outline-none placeholder:text-neutral-500"
            />
            <button
              type="submit"
              className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full bg-neutral-900 px-5 text-sm font-semibold text-white transition-smooth hover:bg-neutral-800"
            >
              <ArrowUp className="h-4 w-4" aria-hidden="true" />
              Plan it
            </button>
          </form>

          <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
            <Proof icon={<Cpu className="h-3.5 w-3.5" />}>Runs on Qualcomm Cloud AI 100 via Cirrascale</Proof>
            <Proof icon={<MapPinned className="h-3.5 w-3.5" />}>Every place checked against Wikipedia</Proof>
            {lastMs ? (
              <Proof icon={<Timer className="h-3.5 w-3.5" />}>Your last trip took {(lastMs / 1000).toFixed(1)}s</Proof>
            ) : null}
          </div>
        </div>

        {/* Slide picker + credit */}
        <div className="absolute bottom-6 right-6 hidden flex-col items-end gap-2 sm:flex sm:bottom-10 sm:right-10">
          <div className="flex gap-1.5" role="tablist" aria-label="Destination photos">
            {DESTINATIONS.map((d, i) => (
              <button
                key={d.place}
                type="button"
                role="tab"
                aria-selected={i === index}
                aria-label={d.place}
                onClick={() => setIndex(i)}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  i === index ? "w-7 bg-white" : "w-1.5 bg-white/50 hover:bg-white/80"
                )}
              />
            ))}
          </div>
          <a href={current.credit} target="_blank" rel="noopener noreferrer" className="text-[10px] text-white/60 hover:text-white hover:underline">
            Photo: Wikimedia Commons
          </a>
        </div>
      </div>
    </section>
  );
}

function Proof({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1.5 font-medium backdrop-blur-md">
      <span aria-hidden="true">{icon}</span>
      {children}
    </span>
  );
}
