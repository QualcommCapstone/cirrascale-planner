"use client";

import "@openuidev/react-ui/index.css";
import { useState } from "react";
import { Renderer } from "@openuidev/react-lang";
import { openuiLibrary } from "@openuidev/react-ui";
import { Loader2, Sparkles } from "lucide-react";
import { selectFocused, useItinerary } from "@/lib/store/itinerary";

export default function AiItineraryInner() {
  const focused = useItinerary(selectFocused);
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forId, setForId] = useState<string | null>(null);

  if (!focused) return null;

  const stale = forId !== focused.id;

  const generate = async () => {
    setLoading(true);
    setError(null);
    setResponse(null);
    setForId(focused.id);

    // The server builds the OpenUI prompt from the stop's data.
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ destination: focused }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Generation failed.");
        return;
      }
      setResponse((data.text as string) ?? "");
    } catch {
      setError("Network error contacting the AI.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          AI detail · OpenUI
        </span>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="rounded-md border border-border px-2 py-1 text-[11px] transition-smooth hover:border-primary/50 hover:text-foreground disabled:opacity-40"
        >
          {loading ? "Generating…" : stale ? `Generate for ${focused.name}` : "Regenerate"}
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
          Composing an interface…
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}

      {response && !stale && !loading && (
        <Renderer response={response} library={openuiLibrary} isStreaming={false} />
      )}

      {!response && !loading && !error && (
        <p className="text-xs text-muted-foreground">
          Generate an AI-rendered panel for {focused.name}.
        </p>
      )}
    </section>
  );
}
