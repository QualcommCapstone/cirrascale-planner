/**
 * Share links without a database: the whole trip, deflated and base64url
 * encoded, goes in the URL hash (#trip=...). The hash never reaches the server.
 */
import { z } from "zod";
import { CATEGORIES, COSTS, MODES, PreferencesSchema, SLOTS, type Trip } from "./types";

const PREFIX = "trip=";

// A shared link is untrusted input: validate its shape before rendering it.
// (Links/images are additionally restricted to https: in format.ts safeUrl.)
const s = (max: number) => z.string().max(max);
const num = z.number().finite();
const PhotoSchema = z.object({ url: s(600), creditUrl: s(600), kind: z.enum(["place", "area", "city"]) });
const ActivitySchema = z.object({
  id: s(120), slot: z.enum(SLOTS), name: s(120), neighborhood: s(100),
  durationMins: num, cost: z.enum(COSTS), category: z.enum(CATEGORIES), reason: s(400),
  lat: num.nullable(), lng: num.nullable(), verified: z.boolean(),
  photo: PhotoSchema.nullable(), sourceUrl: s(600).nullable(),
});
const StopSchema = z.object({
  id: s(120), city: s(100), country: s(100), lat: num, lng: num, dayStart: num, dayEnd: num,
  headline: s(160), intro: s(400), stay: z.object({ area: s(100), why: s(200) }),
  food: z.array(z.object({ name: s(120), note: s(200) })).max(4),
  photo: PhotoSchema.nullable(),
  days: z.array(z.object({ day: num, activities: z.array(ActivitySchema).max(6) })).max(10),
});
const SharedTripSchema = z.object({
  title: s(160), summary: s(400), where: s(100), when: s(100), days: num,
  vibes: z.array(s(40)).max(6), preferences: PreferencesSchema,
  stops: z.array(StopSchema).min(1).max(6),
  legs: z.array(z.object({
    fromId: s(120), toId: s(120), mode: z.enum(MODES), durationMins: num, notes: s(200), estimated: z.boolean(),
  })).max(6),
});

function toBase64Url(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(text: string): Uint8Array<ArrayBuffer> {
  const b64 = text.replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function pipe(bytes: Uint8Array<ArrayBuffer>, stream: CompressionStream | DecompressionStream) {
  const res = new Response(new Blob([bytes]).stream().pipeThrough(stream));
  return new Uint8Array(await res.arrayBuffer());
}

export async function encodeTrip(trip: Trip): Promise<string> {
  const json = new TextEncoder().encode(JSON.stringify(trip));
  return PREFIX + toBase64Url(await pipe(json, new CompressionStream("deflate-raw")));
}

/** Returns null for anything that isn't a valid encoded trip. */
export async function decodeTrip(hash: string): Promise<Trip | null> {
  const value = hash.replace(/^#/, "");
  if (!value.startsWith(PREFIX)) return null;
  try {
    const bytes = await pipe(fromBase64Url(value.slice(PREFIX.length)), new DecompressionStream("deflate-raw"));
    const parsed = SharedTripSchema.safeParse(JSON.parse(new TextDecoder().decode(bytes)));
    return parsed.success ? (parsed.data as Trip) : null;
  } catch {
    return null;
  }
}
