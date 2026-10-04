import Link from "next/link";
import FlipText from "@/components/ui/flip-text";
import { RainbowButton } from "@/components/ui/rainbow-button";
import ModeToggle from "./components/ModeToggle";
import { ArrowRight } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900">
      <header className="w-full py-4 px-6 flex justify-between items-center">
        <div className="text-2xl font-bold">
          <FlipText word="PLANNER" />
        </div>
        <ModeToggle />
      </header>

      <main className="flex-1 flex flex-col items-center justify-center text-center px-6 gap-6">
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-3xl">
          Turn any prompt into a plan.
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-300 max-w-xl">
          Describe a goal and get a clear, structured, step-by-step plan back —
          powered by the Qualcomm AI Inference Suite on Cirrascale.
        </p>
        <Link href="/planner">
          <RainbowButton>
            Start planning
            <ArrowRight className="ml-2 h-4 w-4" />
          </RainbowButton>
        </Link>
      </main>

      <footer className="py-6 text-center text-sm text-gray-500 dark:text-gray-400">
        Inference by Qualcomm Cloud AI 100 Ultra · Cirrascale
      </footer>
    </div>
  );
}
