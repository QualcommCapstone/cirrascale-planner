/**
 * Real places and photos from Wikipedia (server-side, no API key).
 *
 * The model names places; we check them against Wikipedia and keep a place as
 * "verified" only when an article with a matching title sits within
 * VERIFY_RADIUS_KM of the stop. Verified places get the article's coordinates
 * (so globe pins are real) and its free-licensed lead image. Unverified ones
 * are flagged, get no coordinates, and borrow a neighborhood or city photo.
 *
 * Per stop: one geosearch (every article within 10 km of the city centre),
 * matched locally against activity names, then one batched request for photos.
 * Only places outside that circle fall back to a full-text search. This keeps
 * us well inside Wikimedia's rate limits and matches better than search
 * ranking ("Mercado do Bolhão" -> "Bolhão Market").
 */
import { distanceKm, type LatLng } from "../geo";
import type { Photo } from "./types";

const API = "https://en.wikipedia.org/w/api.php";
const USER_AGENT =
  "CirrascalePlanner/0.1 (https://github.com/QualcommCapstone/cirrascale-planner; ASU capstone)";
const TIMEOUT_MS = 6000;
// Wikimedia asks anonymous clients to keep requests (nearly) serial; going wider
// gets 429s quickly. See mediawiki.org/wiki/Wikimedia_APIs/Rate_limits.
const MAX_CONCURRENT = 2;
const CACHE_LIMIT = 500;
const NEARBY_RADIUS_M = 10000; // geosearch maximum
const MAX_FALLBACK_SEARCHES = 12; // per stop; dense cities need more (500 nearby articles may cover only a few km)

/** How far from the stop's city centre a place may be and still count (day trips included). */
export const VERIFY_RADIUS_KM = 40;

export interface WikiPage {
  title: string;
  index?: number;
  fullurl?: string;
  pageimage?: string;
  coordinates?: { lat: number; lon: number }[];
  thumbnail?: { source: string; width: number; height: number };
}

/** A geosearch hit: title + position only. */
export interface NearbyPage {
  title: string;
  lat: number;
  lon: number;
}

export interface CityLocation extends LatLng {
  photo: Photo | null;
}

export interface ActivityPlace {
  verified: boolean;
  lat: number | null;
  lng: number | null;
  photo: Photo | null;
  sourceUrl: string | null;
}

export interface PlaceQuery {
  id: string;
  name: string;
  neighborhood: string;
}

export interface StopRef {
  city: string;
  country: string;
  lat: number;
  lng: number;
  photo: Photo | null;
}

/** The lookups generation needs; swapped for a fake in tests. */
export interface PlacesApi {
  locateCity(city: string, country: string): Promise<CityLocation | null>;
  /** Verify all of one stop's activities. Keyed by activity id. */
  verifyActivities(activities: PlaceQuery[], stop: StopRef): Promise<Map<string, ActivityPlace>>;
}

// --- Matching (pure, unit-tested) ------------------------------------------

/** Words that describe a kind of place rather than name it (incl. common PT/ES/FR/IT/DE). */
const GENERIC = new Set(
  (
    "the of and an at in on to de la le les el los las del da do dos das di du des der die und " +
    "temple shrine market park museum castle garden gardens street alley restaurant cafe bar " +
    "path walk tower palace square district area old town national city center centre beach " +
    "church cathedral bridge hall station food night art gallery house tavern pub " +
    "mercado mercat marche markt museu museo musee jardim jardin giardino palacio palazzo " +
    "castelo castillo chateau castello igreja iglesia eglise chiesa praca plaza piazza place " +
    "rua calle via rue strasse ponte puente pont torre tour catedral cattedrale botanico " +
    "botanical botanique taberna tasca trattoria osteria parque parc praia playa plage " +
    "spiaggia palais fortress fort basilica"
  ).split(" ")
);

/** Lowercase, accent-free word tokens. */
export function tokens(text: string): string[] {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((t) => t.length > 1);
}

function significant(text: string): string[] {
  const all = tokens(text);
  const sig = all.filter((t) => !GENERIC.has(t));
  return sig.length ? sig : all;
}

/** Same word, tolerating plurals/endings ("philosopher"/"philosophers", "botanico"/"botanical"). */
function tokenMatch(a: string, b: string): boolean {
  if (a === b) return true;
  const short = Math.min(a.length, b.length);
  if (short < 5) return false;
  let common = 0;
  while (common < short && a[common] === b[common]) common++;
  return common >= Math.max(5, Math.ceil(short * 0.75));
}

function coverage(from: string[], to: string[]): number {
  if (from.length === 0) return 0;
  return from.filter((w) => to.some((h) => tokenMatch(w, h))).length / from.length;
}

/** Kind-of-place words (any language) -> one canonical kind. */
const KIND: Record<string, string> = {};
for (const [kind, words] of Object.entries({
  market: "market mercado mercat marche markt",
  museum: "museum museu museo musee",
  garden: "garden gardens park jardim jardin giardino parque parc",
  palace: "palace palacio palazzo palais",
  castle: "castle castelo castillo chateau castello fortress fort",
  church: "church cathedral basilica igreja iglesia eglise chiesa catedral cattedrale",
  temple: "temple shrine",
  square: "square praca plaza piazza",
  bridge: "bridge ponte puente pont",
  tower: "tower torre",
  station: "station",
  beach: "beach praia playa plage spiaggia",
  university: "university college school",
  hotel: "hotel",
  stadium: "stadium",
  cemetery: "cemetery",
  hospital: "hospital",
  library: "library",
})) {
  for (const w of words.split(" ")) KIND[w] = kind;
}

function kinds(text: string): string[] {
  return tokens(text).map((t) => KIND[t]).filter(Boolean);
}

/**
 * How well a Wikipedia title names a place, 0 when it doesn't.
 * - Most of the name's distinctive words must be in the title, so "Gion" (a
 *   district) doesn't verify "Gion Nanba" (a restaurant).
 * - Most of the title's distinctive words must be in the name, so "Meiji
 *   Shrine" doesn't match "Meiji Gakuin University".
 * - If both say what kind of place they are, the kinds must agree, so
 *   "Mercado do Bolhão" (a market) doesn't match "Bolhão station".
 */
export function matchScore(name: string, title: string): number {
  const bareTitle = title.replace(/\s*\(.*\)\s*$/, ""); // "National Pantheon (Portugal)"

  const nameKinds = kinds(name);
  const titleKinds = kinds(bareTitle);
  if (nameKinds.length && titleKinds.length && !titleKinds.some((k) => nameKinds.includes(k)))
    return 0;

  // Same words, different spacing/hyphenation: "Shinjuku Gyoen" vs "Shinjuku Gyo-en".
  const compact = (t: string) => significant(t).join("");
  if (compact(name).length >= 6 && compact(name) === compact(bareTitle)) return 1.5;

  const forward = coverage(significant(name), tokens(bareTitle));
  const reverse = coverage(significant(bareTitle), tokens(name));
  if (forward < 0.75 || reverse < 0.6) return 0;
  return forward + 0.5 * reverse;
}

export function nameMatches(name: string, title: string): boolean {
  return matchScore(name, title) > 0;
}

/** Same name, ignoring a trailing qualifier: "Nara" equals "Nara (city)". */
function sameText(a: string, b: string): boolean {
  const bare = (t: string) => tokens(t.replace(/\s*\(.*\)\s*$/, "")).join(" ");
  return bare(a) === bare(b);
}

/**
 * Best-matching nearby article for a name, or null. Excludes the city/country
 * pages. With `area`, only plain place pages count, so the neighborhood
 * "Cais do Sodré" doesn't pick up "Cais do Sodré station".
 */
export function matchNearby(
  name: string,
  nearby: NearbyPage[],
  exclude: string[] = [],
  { area = false }: { area?: boolean } = {}
): NearbyPage | null {
  let best: NearbyPage | null = null;
  let bestScore = 0;
  for (const p of nearby) {
    if (exclude.some((x) => sameText(x, p.title))) continue;
    if (area && kinds(p.title.replace(/\s*\(.*\)\s*$/, "")).length > 0) continue;
    const s = matchScore(name, p.title);
    if (s > bestScore) {
      best = p;
      bestScore = s;
    }
  }
  return best;
}

function coords(page: WikiPage): LatLng | null {
  const c = page.coordinates?.[0];
  return c ? { lat: c.lat, lng: c.lon } : null;
}

/** First full-text result (in rank order) that names `name` and lies near `near`. */
export function pickPage(
  pages: WikiPage[],
  opts: { name: string; near?: LatLng; radiusKm?: number; exclude?: string[] }
): WikiPage | null {
  const ranked = [...pages].sort((a, b) => (a.index ?? 0) - (b.index ?? 0));
  for (const p of ranked) {
    const at = coords(p);
    if (!at) continue;
    if (opts.exclude?.some((x) => sameText(x, p.title))) continue;
    if (!nameMatches(opts.name, p.title)) continue;
    if (opts.near && distanceKm(opts.near, at) > (opts.radiusKm ?? VERIFY_RADIUS_KM)) continue;
    return p;
  }
  return null;
}

/** Lead images that aren't photos of the place (logos, maps, flags, diagrams). */
const NOT_A_PHOTO = /logo|wordmark|emblem|coat[_ ]of[_ ]arms|flag|map|locator|diagram|icon|seal|\.svg$/i;

export function photoFrom(page: WikiPage, kind: Photo["kind"]): Photo | null {
  if (!page.thumbnail?.source) return null;
  if (NOT_A_PHOTO.test(page.pageimage ?? "")) return null;
  return {
    // Drop Wikimedia's tracking query string; the bare thumbnail URL is stable.
    url: page.thumbnail.source.split("?")[0],
    creditUrl: page.pageimage
      ? `https://en.wikipedia.org/wiki/File:${encodeURIComponent(page.pageimage)}`
      : page.fullurl ?? "https://en.wikipedia.org",
    kind,
  };
}

// --- Network ---------------------------------------------------------------

/** While rate-limited (429), skip lookups until this time instead of piling on. */
let pausedUntil = 0;
let active = 0;
const waiting: (() => void)[] = [];
const cache = new Map<string, Promise<unknown>>();

export function isRateLimited(): boolean {
  return Date.now() < pausedUntil;
}

async function limited<T>(fn: () => Promise<T>): Promise<T> {
  if (active >= MAX_CONCURRENT) await new Promise<void>((r) => waiting.push(r));
  active++;
  try {
    return await fn();
  } finally {
    active--;
    waiting.shift()?.();
  }
}

/** One API call. Returns null on any failure (offline, timeout, rate limit). */
async function api<T>(params: Record<string, string>): Promise<T | null> {
  const qs = new URLSearchParams({ action: "query", format: "json", formatversion: "2", ...params });
  return limited(async () => {
    if (isRateLimited()) return null;
    try {
      const res = await fetch(`${API}?${qs}`, {
        headers: { "User-Agent": USER_AGENT, "Api-User-Agent": USER_AGENT },
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      if (res.status === 429) {
        const wait = Number(res.headers.get("retry-after")) || 30;
        pausedUntil = Date.now() + wait * 1000;
        console.warn(`[places] Wikipedia rate limit; pausing lookups for ${wait}s`);
        return null;
      }
      return res.ok ? ((await res.json()) as T) : null;
    } catch {
      return null;
    }
  });
}

/** Cache successful results only, so a failed lookup can be retried later. */
function cached<T>(key: string, load: () => Promise<T | null>): Promise<T | null> {
  const hit = cache.get(key) as Promise<T | null> | undefined;
  if (hit) return hit;
  const p = load().then((v) => {
    if (v === null) cache.delete(key);
    return v;
  });
  if (cache.size >= CACHE_LIMIT) cache.delete(cache.keys().next().value as string);
  cache.set(key, p);
  return p;
}

const PAGE_PROPS = {
  prop: "coordinates|pageimages|info",
  inprop: "url",
  colimit: "max",
  piprop: "thumbnail|name",
  pilicense: "free",
};

function search(query: string, thumbSize: number): Promise<WikiPage[] | null> {
  return cached(`s|${thumbSize}|${query.toLowerCase()}`, async () => {
    const data = await api<{ query?: { pages?: WikiPage[] } }>({
      ...PAGE_PROPS,
      generator: "search",
      gsrsearch: query,
      gsrlimit: "5",
      gsrnamespace: "0",
      pithumbsize: String(thumbSize),
    });
    return data ? data.query?.pages ?? [] : null;
  });
}

function nearbyPages(at: LatLng): Promise<NearbyPage[] | null> {
  const key = `n|${at.lat.toFixed(3)}|${at.lng.toFixed(3)}`;
  return cached(key, async () => {
    const data = await api<{ query?: { geosearch?: NearbyPage[] } }>({
      list: "geosearch",
      gscoord: `${at.lat}|${at.lng}`,
      gsradius: String(NEARBY_RADIUS_M),
      gslimit: "500",
      gsnamespace: "0",
    });
    return data ? data.query?.geosearch ?? [] : null;
  });
}

/** Photos/urls for up to 50 titles in one request. */
async function pageDetails(titles: string[], thumbSize: number): Promise<Map<string, WikiPage>> {
  const out = new Map<string, WikiPage>();
  for (let i = 0; i < titles.length; i += 50) {
    const batch = titles.slice(i, i + 50);
    const data = await api<{ query?: { pages?: WikiPage[] } }>({
      ...PAGE_PROPS,
      titles: batch.join("|"),
      pithumbsize: String(thumbSize),
      pilimit: "50",
    });
    for (const p of data?.query?.pages ?? []) out.set(p.title, p);
  }
  return out;
}

export const wikipediaPlaces: PlacesApi = {
  async locateCity(city, country) {
    const pages = await search(`${city} ${country}`.trim(), 1280);
    const page = pickPage(pages ?? [], { name: city });
    const at = page && coords(page);
    if (!page || !at) return null;
    return { ...at, photo: photoFrom(page, "city") };
  },

  async verifyActivities(activities, stop) {
    const center = { lat: stop.lat, lng: stop.lng };
    const exclude = [stop.city, stop.country];
    const nearby = (await nearbyPages(center)) ?? [];

    // 1. Match names against articles near the city centre.
    const placeTitle = new Map<string, NearbyPage>();
    const areaTitle = new Map<string, NearbyPage>();
    const unmatched: PlaceQuery[] = [];
    for (const a of activities) {
      const hit = matchNearby(a.name, nearby, exclude);
      if (hit) placeTitle.set(a.id, hit);
      else unmatched.push(a);
      const area = a.neighborhood ? matchNearby(a.neighborhood, nearby, exclude, { area: true }) : null;
      if (area) areaTitle.set(a.id, area);
    }

    // 2. Places outside the circle (day trips): a few full-text searches.
    const searched = new Map<string, WikiPage>();
    for (const a of unmatched.slice(0, MAX_FALLBACK_SEARCHES)) {
      const page = pickPage((await search(`${a.name} ${stop.city}`, 640)) ?? [], {
        name: a.name,
        near: center,
        exclude,
      });
      if (page) searched.set(a.id, page);
    }

    // 3. One batched request for the photos of everything matched nearby.
    const matched = Array.from(placeTitle.values()).concat(Array.from(areaTitle.values()));
    const titles = matched.map((p) => p.title).filter((t, i, all) => all.indexOf(t) === i);
    const details = await pageDetails(titles, 640);

    const out = new Map<string, ActivityPlace>();
    for (const a of activities) {
      const near = placeTitle.get(a.id);
      const page = near ? details.get(near.title) ?? { title: near.title } : searched.get(a.id);
      const at = near ? { lat: near.lat, lng: near.lon } : page && coords(page);
      if (page && at) {
        out.set(a.id, {
          verified: true,
          lat: at.lat,
          lng: at.lng,
          photo: photoFrom(page, "place") ?? stop.photo,
          sourceUrl: page.fullurl ?? `https://en.wikipedia.org/wiki/${encodeURIComponent(page.title)}`,
        });
        continue;
      }
      // Not verifiable: no pin, but show the neighborhood (or city) photo.
      const area = areaTitle.get(a.id);
      const areaPage = area && details.get(area.title);
      out.set(a.id, {
        verified: false,
        lat: null,
        lng: null,
        photo: (areaPage && photoFrom(areaPage, "area")) ?? stop.photo,
        sourceUrl: null,
      });
    }
    return out;
  },
};
