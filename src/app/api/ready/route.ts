import { NextResponse } from "next/server";
import { complete, DEFAULT_MODEL } from "@/lib/cirrascale";

// Readiness != liveness. /api/health says "the process is up"; this says
// "the Cirrascale inference backend is reachable and answering." It makes a
// tiny real completion, so it exercises auth + the endpoint end-to-end.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const model = process.env.CIRRASCALE_MODEL ?? DEFAULT_MODEL;
  const startedAt = Date.now();

  try {
    await complete("ping", { maxTokens: 1 });
    return NextResponse.json({
      ready: true,
      backend: "cirrascale",
      model,
      latencyMs: Date.now() - startedAt,
    });
  } catch (err) {
    const error = err instanceof Error ? err.message : "unknown error";
    return NextResponse.json(
      { ready: false, backend: "cirrascale", model, error },
      { status: 503 }
    );
  }
}
