/**
 * Tiny city/place -> lat,lng fallback table.
 *
 * The model is asked to return coordinates, but when it omits them or returns
 * something off, we look the destination name up here. Case/substring tolerant.
 * Not exhaustive — just enough common destinations for a believable globe.
 */
export interface LatLng {
  lat: number;
  lng: number;
}

const CITIES: Record<string, LatLng> = {
  tokyo: { lat: 35.6762, lng: 139.6503 },
  kyoto: { lat: 35.0116, lng: 135.7681 },
  osaka: { lat: 34.6937, lng: 135.5023 },
  hiroshima: { lat: 34.3853, lng: 132.4553 },
  sapporo: { lat: 43.0618, lng: 141.3545 },
  seoul: { lat: 37.5665, lng: 126.978 },
  beijing: { lat: 39.9042, lng: 116.4074 },
  shanghai: { lat: 31.2304, lng: 121.4737 },
  "hong kong": { lat: 22.3193, lng: 114.1694 },
  bangkok: { lat: 13.7563, lng: 100.5018 },
  singapore: { lat: 1.3521, lng: 103.8198 },
  "kuala lumpur": { lat: 3.139, lng: 101.6869 },
  bali: { lat: -8.3405, lng: 115.092 },
  jakarta: { lat: -6.2088, lng: 106.8456 },
  "hanoi": { lat: 21.0278, lng: 105.8342 },
  "ho chi minh city": { lat: 10.8231, lng: 106.6297 },
  delhi: { lat: 28.6139, lng: 77.209 },
  mumbai: { lat: 19.076, lng: 72.8777 },
  jaipur: { lat: 26.9124, lng: 75.7873 },
  dubai: { lat: 25.2048, lng: 55.2708 },
  istanbul: { lat: 41.0082, lng: 28.9784 },
  cairo: { lat: 30.0444, lng: 31.2357 },
  "cape town": { lat: -33.9249, lng: 18.4241 },
  nairobi: { lat: -1.2921, lng: 36.8219 },
  marrakesh: { lat: 31.6295, lng: -7.9811 },
  marrakech: { lat: 31.6295, lng: -7.9811 },
  london: { lat: 51.5074, lng: -0.1278 },
  paris: { lat: 48.8566, lng: 2.3522 },
  amsterdam: { lat: 52.3676, lng: 4.9041 },
  berlin: { lat: 52.52, lng: 13.405 },
  rome: { lat: 41.9028, lng: 12.4964 },
  florence: { lat: 43.7696, lng: 11.2558 },
  venice: { lat: 45.4408, lng: 12.3155 },
  barcelona: { lat: 41.3851, lng: 2.1734 },
  madrid: { lat: 40.4168, lng: -3.7038 },
  lisbon: { lat: 38.7223, lng: -9.1393 },
  porto: { lat: 41.1579, lng: -8.6291 },
  prague: { lat: 50.0755, lng: 14.4378 },
  vienna: { lat: 48.2082, lng: 16.3738 },
  athens: { lat: 37.9838, lng: 23.7275 },
  santorini: { lat: 36.3932, lng: 25.4615 },
  zurich: { lat: 47.3769, lng: 8.5417 },
  reykjavik: { lat: 64.1466, lng: -21.9426 },
  "new york": { lat: 40.7128, lng: -74.006 },
  "new york city": { lat: 40.7128, lng: -74.006 },
  "san francisco": { lat: 37.7749, lng: -122.4194 },
  "los angeles": { lat: 34.0522, lng: -118.2437 },
  "las vegas": { lat: 36.1699, lng: -115.1398 },
  chicago: { lat: 41.8781, lng: -87.6298 },
  miami: { lat: 25.7617, lng: -80.1918 },
  "mexico city": { lat: 19.4326, lng: -99.1332 },
  "rio de janeiro": { lat: -22.9068, lng: -43.1729 },
  "buenos aires": { lat: -34.6037, lng: -58.3816 },
  lima: { lat: -12.0464, lng: -77.0428 },
  cusco: { lat: -13.5319, lng: -71.9675 },
  sydney: { lat: -33.8688, lng: 151.2093 },
  melbourne: { lat: -37.8136, lng: 144.9631 },
  auckland: { lat: -36.8509, lng: 174.7645 },
  queenstown: { lat: -45.0312, lng: 168.6626 },
  toronto: { lat: 43.6532, lng: -79.3832 },
  vancouver: { lat: 49.2827, lng: -123.1207 },
};

/** Look up coordinates by place name; tolerant of case and substrings. */
export function lookupLatLng(name: string): LatLng | null {
  if (!name) return null;
  const key = name.trim().toLowerCase();
  if (CITIES[key]) return CITIES[key];
  // substring either direction (e.g. "Kyoto, Japan" or "central tokyo")
  for (const [city, coords] of Object.entries(CITIES)) {
    if (key.includes(city) || city.includes(key)) return coords;
  }
  return null;
}

/** A valid-looking coordinate pair on Earth. */
export function isValidLatLng(lat: unknown, lng: unknown): lat is number {
  return (
    typeof lat === "number" &&
    typeof lng === "number" &&
    Number.isFinite(lat) &&
    Number.isFinite(lng) &&
    lat >= -90 &&
    lat <= 90 &&
    lng >= -180 &&
    lng <= 180 &&
    !(lat === 0 && lng === 0)
  );
}
