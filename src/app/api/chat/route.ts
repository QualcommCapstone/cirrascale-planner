import { NextResponse } from "next/server";
import { z } from "zod";
import { complete } from "@/lib/cirrascale";
import { getOpenUiSystemPrompt } from "@/lib/openui";
import { buildDetailPrompt } from "@/lib/planner";

export const runtime = "nodejs";

const MAX_TOKENS = 900;

// Length limits keep the fields from being used to smuggle in a free-form prompt.
const StopSchema = z.object({
  name: z.string().trim().min(1).max(100),
  country: z.string().max(100),
  dayStart: z.number().int().min(1).max(60),
  dayEnd: z.number().int().min(1).max(60),
  summary: z.string().max(500),
  activities: z.array(z.string().max(200)).max(6),
});

/**
 * OpenUI detail panel for one trip stop.
 *
 * The client sends only the stop's data; the prompt (OpenUI system prompt +
 * instruction) is assembled here, so this route can't be used as a general
 * completion proxy for our key.
 */
export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const parsed = StopSchema.safeParse((body as { destination?: unknown })?.destination);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid 'destination'." }, { status: 400 });
  }

  try {
    const prompt = buildDetailPrompt(getOpenUiSystemPrompt(), parsed.data);
    const text = await complete(prompt, { maxTokens: MAX_TOKENS });
    return NextResponse.json({ text });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
