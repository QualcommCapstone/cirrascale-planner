/**
 * Day-by-day weather from Open-Meteo (server-side, no API key, no rate limit
 * for this volume). Sem 1 scope only: show the forecast on the initial plan.
 *
 * shortcut: the trip has no real start date yet (`Trip.when` is free text, see
 * normalize.ts), so day 1 is assumed to start today. A day outside Open-Meteo's
 * 16-day window is simply left without weather. Upgrade once trips carry a real
 * date and this can become the Sem 2 "dynamic recheck".
 */
import type { LatLng } from "../geo";

const API = "https://api.open-meteo.com/v1/forecast";
const FORECAST_DAYS = 16;
const TIMEOUT_MS = 5000;
const HOT_C = 33;

export const WEATHER_CONDITIONS = ["clear", "cloudy", "rain", "snow", "stormy", "hot"] as const;
export type WeatherCondition = (typeof WEATHER_CONDITIONS)[number];

export interface DayWeather {
  condition: WeatherCondition;
  highC: number;
  lowC: number;
  precipitationChance: number;
  indoorAdvised: boolean;
}

/** The lookup generation needs; swapped for a fake (or the no-op) in tests. */
export interface WeatherApi {
  /** Forecast keyed by ISO date (YYYY-MM-DD) in the location's local timezone. */
  forecast(at: LatLng): Promise<Map<string, DayWeather>>;
}

// WMO weather codes: https://open-meteo.com/en/docs
const STORMY = new Set([95, 96, 99]);
const SNOW = new Set([71, 73, 75, 77, 85, 86]);
const RAIN = new Set([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]);
const CLOUDY = new Set([1, 2, 3, 45, 48]);

/** WMO weather code + forecast high -> a condition simple enough to plan around. */
export function conditionFromCode(code: number, highC: number): WeatherCondition {
  if (STORMY.has(code)) return "stormy";
  if (SNOW.has(code)) return "snow";
  if (RAIN.has(code)) return "rain";
  if (highC >= HOT_C) return "hot";
  if (CLOUDY.has(code)) return "cloudy";
  return "clear";
}

export function indoorAdvised(condition: WeatherCondition): boolean {
  return condition === "rain" || condition === "snow" || condition === "stormy" || condition === "hot";
}

interface OpenMeteoResponse {
  daily?: {
    time: string[];
    weathercode: number[];
    temperature_2m_max: number[];
    temperature_2m_min: number[];
    precipitation_probability_max: number[];
  };
}

/** Does nothing: the default for tests, and for callers that don't want weather. */
export const noopWeatherApi: WeatherApi = {
  async forecast() {
    return new Map();
  },
};

const cache = new Map<string, Promise<Map<string, DayWeather>>>();

export const openMeteoWeather: WeatherApi = {
  forecast(at) {
    const key = `${at.lat.toFixed(2)},${at.lng.toFixed(2)}`;
    const hit = cache.get(key);
    if (hit) return hit;

    const p = (async (): Promise<Map<string, DayWeather>> => {
      const qs = new URLSearchParams({
        latitude: String(at.lat),
        longitude: String(at.lng),
        daily: "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        timezone: "auto",
        forecast_days: String(FORECAST_DAYS),
      });
      try {
        const res = await fetch(`${API}?${qs}`, { signal: AbortSignal.timeout(TIMEOUT_MS) });
        if (!res.ok) return new Map();
        const data = (await res.json()) as OpenMeteoResponse;
        const d = data.daily;
        if (!d) return new Map();
        const out = new Map<string, DayWeather>();
        d.time.forEach((date, i) => {
          const highC = d.temperature_2m_max[i];
          const condition = conditionFromCode(d.weathercode[i], highC);
          out.set(date, {
            condition,
            highC,
            lowC: d.temperature_2m_min[i],
            precipitationChance: d.precipitation_probability_max[i] ?? 0,
            indoorAdvised: indoorAdvised(condition),
          });
        });
        return out;
      } catch {
        return new Map();
      }
    })();
    cache.set(key, p);
    return p;
  },
};
