import type { Feeling } from "@/types/api";

/** The feeling scale: values map to five weather tokens (design system "The feeling scale"). */
export const WEATHER = [
  { level: 1, name: "Rainy", token: "var(--weather-1)", icon: "rain" },
  { level: 2, name: "Drizzly", token: "var(--weather-2)", icon: "drizzle" },
  { level: 3, name: "Cloudy", token: "var(--weather-3)", icon: "cloud" },
  { level: 4, name: "Sunny", token: "var(--weather-4)", icon: "sun" },
  { level: 5, name: "Golden", token: "var(--weather-5)", icon: "golden" },
] as const;

export type Weather = (typeof WEATHER)[number];

export function weatherFor(value: number): Weather {
  const v = Math.min(10, Math.max(1, value));
  const idx = Math.min(4, Math.floor((Math.round(v) - 1) / 2));
  return WEATHER[idx] as Weather;
}

/** Stress and anxiety: higher is harder, so they use the neutral sky tone instead. */
export function usesWeather(feeling: Feeling): boolean {
  return feeling !== "stress" && feeling !== "anxiety";
}

export function fillFor(feeling: Feeling, value: number): string {
  return usesWeather(feeling) ? weatherFor(value).token : "var(--sky-tint)";
}

export const FEELING_COPY: Record<Feeling, { label: string; low: string; high: string }> = {
  mood: { label: "Mood", low: "heavy", high: "bright" },
  energy: { label: "Energy", low: "drained", high: "full of beans" },
  stress: { label: "Stress", low: "calm", high: "stretched thin" },
  anxiety: { label: "Worry", low: "settled", high: "on edge" },
  focus: { label: "Focus", low: "scattered", high: "locked in" },
};

/** Forecast as weather, not a verdict: "Sunny, likely between 6.2 and 8.0". */
export function forecastPhrase(feeling: Feeling, predicted: number, lower: number, upper: number): string {
  const range = `likely between ${lower.toFixed(1)} and ${upper.toFixed(1)}`;
  if (!usesWeather(feeling)) {
    const word = predicted >= 7 ? "A fuller day" : predicted >= 4 ? "A steady day" : "A lighter day";
    return `${word}, ${range}`;
  }
  return `${weatherFor(predicted).name}, ${range}`;
}
