import { Globe2, MessageSquareText, SlidersHorizontal } from "lucide-react";
import { Hero } from "@/components/landing/Hero";
import { LandingSamples } from "@/components/landing/LandingSamples";

const STEPS = [
  {
    icon: MessageSquareText,
    title: "Say it like you'd text a friend",
    body: "“A week in Morocco from Marrakesh's souks to the blue city.” Dates, length and vibe are all optional.",
  },
  {
    icon: SlidersHorizontal,
    title: "Tune it to you",
    body: "Pick interests, budget and pace. They shape which places, restaurants and neighborhoods you get.",
  },
  {
    icon: Globe2,
    title: "See it, then go",
    body: "Real places with photos, morning to evening, train times between cities, and the route on a globe.",
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Hero />

      <main className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
        <section aria-labelledby="how">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">How it works</p>
          <h2 id="how" className="mt-3 max-w-2xl text-3xl font-bold leading-tight tracking-display text-balance sm:text-4xl">
            From one sentence to a trip you can picture.
          </h2>
          <ol className="mt-10 grid gap-8 sm:grid-cols-3">
            {STEPS.map(({ icon: Icon, title, body }, i) => (
              <li key={title}>
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-muted">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h3 className="mt-4 text-lg font-bold tracking-display">
                  <span className="text-muted-foreground">0{i + 1} </span>
                  {title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="try" className="mt-24">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Try one</p>
              <h2 id="try" className="mt-3 text-3xl font-bold leading-tight tracking-display sm:text-4xl">
                Start from a place
              </h2>
            </div>
          </div>
          <div className="mt-8">
            <LandingSamples />
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-xs text-muted-foreground sm:px-8">
          <span>Cirrascale Planner · ASU capstone sponsored by Qualcomm</span>
          <span>Inference on Qualcomm Cloud AI 100 via Cirrascale · Places and photos from Wikipedia</span>
        </div>
      </footer>
    </div>
  );
}
