import { NextResponse } from "next/server";
import { complete, KNOWN_MODELS } from "@/lib/cirrascale";
import { buildPlannerPrompt, extractPlan } from "@/lib/planner";

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
    const raw = await complete(prompt, {
      model: body.model,
      maxTokens: 1024,
    });
    return NextResponse.json({ plan: extractPlan(raw) });
  } catch (err) {
    // Log the real error here; upstream response details stay off the client.
    console.error("[api/plan]", err);
    return NextResponse.json({ error: "The model request failed. Try again." }, { status: 502 });
  }
}

// Handy for a model picker in the UI.
export async function GET() {
  return NextResponse.json({ models: KNOWN_MODELS });
}
