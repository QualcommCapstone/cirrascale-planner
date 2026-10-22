import { NextResponse } from "next/server";

// Health checks must reflect live state, never a cached/static response.
export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    status: "ok",
    service: "cirrascale-planner",
    timestamp: new Date().toISOString(),
  });
}
