import { describe, expect, it } from "vitest";

import { checkInSchema, metricSchema, signupSchema } from "@/lib/schemas";

const base = {
  mood: 6, energy: 5, stress: 4, anxiety: 3, focus: 7,
  sleep_hours: "", sleep_quality: "", exercise_minutes: "", outdoor_minutes: "",
  screen_time_hours: "", caffeine_servings: "", alcohol_units: "", meals_eaten: "",
  social_interaction: "", workload: "", tags: [], notes: "", custom_metrics: {},
};

describe("check-in form validation", () => {
  it("accepts the five feelings with every optional field empty", () => {
    const r = checkInSchema.safeParse(base);
    expect(r.success).toBe(true);
    if (r.success) {
      expect(r.data.sleep_hours).toBeNull();
      expect(r.data.workload).toBeNull();
    }
  });

  it("requires every core feeling", () => {
    const r = checkInSchema.safeParse({ ...base, mood: undefined, focus: undefined });
    expect(r.success).toBe(false);
    if (!r.success) {
      const paths = r.error.issues.map((i) => i.path[0]);
      expect(paths).toContain("mood");
      expect(paths).toContain("focus");
    }
  });

  it("rejects out-of-range values with friendly messages", () => {
    const r = checkInSchema.safeParse({ ...base, mood: 11, sleep_hours: "25", meals_eaten: "2.5" });
    expect(r.success).toBe(false);
    if (!r.success) {
      const msgs = Object.fromEntries(r.error.issues.map((i) => [String(i.path[0]), i.message]));
      expect(msgs.mood).toMatch(/1 to 10/);
      expect(msgs.sleep_hours).toMatch(/at most 24/);
      expect(msgs.meals_eaten).toMatch(/whole number/);
    }
  });

  it("converts numeric strings and limits notes", () => {
    const r = checkInSchema.safeParse({ ...base, sleep_hours: "7.5", custom_metrics: { "3": "2" } });
    expect(r.success && r.data.sleep_hours).toBe(7.5);
    expect(r.success && r.data.custom_metrics["3"]).toBe(2);
    expect(checkInSchema.safeParse({ ...base, notes: "x".repeat(2001) }).success).toBe(false);
  });
});

describe("other forms", () => {
  it("signup needs a name, an email and 8+ characters", () => {
    expect(signupSchema.safeParse({ display_name: "Sid", email: "a@b.co", password: "12345678" }).success).toBe(true);
    expect(signupSchema.safeParse({ display_name: "", email: "nope", password: "short" }).success).toBe(false);
  });

  it("trackers need max above min", () => {
    expect(metricSchema.safeParse({ name: "Practice", min: 0, max: 5 }).success).toBe(true);
    const r = metricSchema.safeParse({ name: "Practice", min: 5, max: 5 });
    expect(r.success).toBe(false);
  });
});
