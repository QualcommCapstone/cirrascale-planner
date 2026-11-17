import { describe, it, expect, vi, afterEach } from "vitest";
import { POST } from "@/app/api/itinerary/route";

const VALID_BODY = JSON.stringify({
  goal: "6 days in Japan",
  preferences: { interests: [], budget: "Mid", pace: "Balanced" },
});

function req(body: string) {
  return new Request("http://localhost/api/itinerary", {
    method: "POST",
    body,
    headers: { "content-type": "application/json" },
  });
}

describe("/api/itinerary backend selection", () => {
  const origFetch = global.fetch;
  const origEnv = process.env.BACKEND_URL;

  afterEach(() => {
    global.fetch = origFetch;
    if (origEnv === undefined) delete process.env.BACKEND_URL;
    else process.env.BACKEND_URL = origEnv;
    vi.restoreAllMocks();
  });

  it("proxies to the backend and streams NDJSON through when BACKEND_URL is set", async () => {
    process.env.BACKEND_URL = "http://backend.test";
    const upstream = '{"type":"outline"}\n{"type":"done","ms":1}\n';
    const fetchMock = vi.fn(async (url: string) => {
      expect(url).toBe("http://backend.test/api/v1/plan");
      return new Response(upstream, {
        status: 200,
        headers: { "content-type": "application/x-ndjson" },
      });
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const res = await POST(req(VALID_BODY));
    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toContain("x-ndjson");
    expect(await res.text()).toBe(upstream); // piped through unchanged
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns 502 when the backend is unreachable", async () => {
    process.env.BACKEND_URL = "http://backend.test";
    global.fetch = vi.fn(async () => {
      throw new Error("ECONNREFUSED");
    }) as unknown as typeof fetch;
    const res = await POST(req(VALID_BODY));
    expect(res.status).toBe(502);
  });

  it("rejects an invalid body with 400 before touching any backend", async () => {
    delete process.env.BACKEND_URL;
    const res = await POST(req(JSON.stringify({})));
    expect(res.status).toBe(400);
  });
});
