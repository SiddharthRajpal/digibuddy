import { describe, expect, it } from "vitest";

import { addDays, diffDays, todayIn } from "@/lib/dates";
import { fillFor, forecastPhrase, usesWeather, weatherFor } from "@/lib/feelings";

describe("dates", () => {
  it("uses the user's timezone for today", () => {
    // 15:30 UTC is 23:30 in Singapore (same day) and 00:30 next day is 16:30 UTC.
    expect(todayIn("Asia/Singapore", new Date("2026-10-14T15:30:00Z"))).toBe("2026-10-14");
    expect(todayIn("Asia/Singapore", new Date("2026-10-14T16:30:00Z"))).toBe("2026-10-15");
    expect(todayIn("Europe/London", new Date("2026-10-14T16:30:00Z"))).toBe("2026-10-14");
  });

  it("adds and diffs days across month ends", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
    expect(diffDays("2026-10-14", "2026-10-11")).toBe(3);
  });
});

describe("feeling scale", () => {
  it("maps values to the five weather tokens", () => {
    expect([1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((v) => weatherFor(v).name)).toEqual([
      "Rainy", "Rainy", "Drizzly", "Drizzly", "Cloudy", "Cloudy", "Sunny", "Sunny", "Golden", "Golden",
    ]);
  });

  it("never colors stress or worry with weather", () => {
    expect(usesWeather("stress")).toBe(false);
    expect(usesWeather("anxiety")).toBe(false);
    expect(fillFor("stress", 9)).toBe("var(--sky-tint)");
    expect(fillFor("mood", 9)).toBe("var(--weather-5)");
  });

  it("phrases forecasts as weather with a range, never a promise", () => {
    expect(forecastPhrase("mood", 7.2, 5.2, 8.9)).toBe("Sunny, likely between 5.2 and 8.9");
    expect(forecastPhrase("stress", 6.8, 4.9, 8.8)).toMatch(/likely between 4.9 and 8.8/);
  });
});
