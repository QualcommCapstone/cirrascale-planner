import { NextResponse } from "next/server";
import { complete } from "@/lib/cirrascale";

export const runtime = "nodejs";

interface ChatRequest {
  prompt?: string;
  maxTokens?: number;
}

/**
 * Generic Cirrascale completion proxy for the OpenUI detail panel.
 *
 * The OpenUI system prompt (which describes the component library) is assembled
 * on the client and sent here as a single `prompt`, so this route stays a thin
 * text-in / text-out wrapper around the one Cirrascale integration point.
 */
export async function POST(req: Request) {
  let body: ChatRequest;
  try {
    body = (await req.json()) as ChatRequest;
  } catch {
    return NextResponse.json({ error: "Invalid JSON body." }, { status: 400 });
  }

  const prompt = body.prompt?.trim();
  if (!prompt) {
    return NextResponse.json({ error: "Missing 'prompt'." }, { status: 400 });
  }

  try {
    const text = await complete(prompt, { maxTokens: body.maxTokens ?? 900 });
    return NextResponse.json({ text });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error.";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
