import { NextResponse } from "next/server";
import { complete, KNOWN_MODELS } from "@/lib/cirrascale";
import { buildPlannerPrompt } from "@/lib/planner";

export const runtime = "nodejs";

interface PlanRequest {
  goal?: string;
  context?: string;
  model?: string;
}

export async function POST(req: Request) {
  let body: PlanRequest;
  try {
    body = (await req.json()) as PlanRequest;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const goal = body.goal?.trim();
  if (!goal) {
    return NextResponse.json({ error: "Missing 'goal'." }, { status: 400 });
  }

  const prompt = buildPlannerPrompt(goal, body.context);

  try {
    const plan = await complete(prompt, {
      model: body.model,
      maxTokens: 1024,
    });
    return NextResponse.json({ plan });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}

// Handy for a model picker in the UI.
export async function GET() {
  return NextResponse.json({ models: KNOWN_MODELS });
}
