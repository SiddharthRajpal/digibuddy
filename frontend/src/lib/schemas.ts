/** Form validation (zod). Mirrors the API's limits so users see errors before submitting. */
import { z } from "zod";

const feeling = z
  .number({ required_error: "Pick a number from 1 to 10.", invalid_type_error: "Pick a number from 1 to 10." })
  .int()
  .min(1, "Pick a number from 1 to 10.")
  .max(10, "Pick a number from 1 to 10.");

/** Optional number: empty input becomes null. */
function optionalNumber(min: number, max: number, opts: { int?: boolean; label: string }) {
  return z.preprocess(
    (v) => (v === "" || v === undefined || v === null || Number.isNaN(v) ? null : Number(v)),
    z
      .number({ invalid_type_error: `${opts.label} must be a number.` })
      .min(min, `${opts.label} must be at least ${min}.`)
      .max(max, `${opts.label} must be at most ${max}.`)
      .refine((n) => !opts.int || Number.isInteger(n), `${opts.label} must be a whole number.`)
      .nullable(),
  );
}

export const checkInSchema = z.object({
  mood: feeling,
  energy: feeling,
  stress: feeling,
  anxiety: feeling,
  focus: feeling,
  sleep_hours: optionalNumber(0, 24, { label: "Sleep" }),
  sleep_quality: optionalNumber(1, 5, { int: true, label: "Sleep quality" }),
  exercise_minutes: optionalNumber(0, 1440, { int: true, label: "Exercise" }),
  outdoor_minutes: optionalNumber(0, 1440, { int: true, label: "Time outdoors" }),
  screen_time_hours: optionalNumber(0, 24, { label: "Screen time" }),
  caffeine_servings: optionalNumber(0, 50, { int: true, label: "Caffeine" }),
  alcohol_units: optionalNumber(0, 100, { int: true, label: "Alcohol" }),
  meals_eaten: optionalNumber(0, 5, { int: true, label: "Meals" }),
  social_interaction: optionalNumber(1, 5, { int: true, label: "Time with people" }),
  workload: optionalNumber(1, 5, { int: true, label: "Workload" }),
  tags: z.array(z.string().trim().min(1).max(32)).max(20, "Up to 20 tags."),
  notes: z.string().max(2000, "Notes can be up to 2,000 characters.").optional().nullable(),
  custom_metrics: z.record(z.string(), z.preprocess(
    (v) => (v === "" || v === undefined || v === null || Number.isNaN(v) ? null : Number(v)),
    z.number().nullable(),
  )),
});

export type CheckInFormInput = z.input<typeof checkInSchema>;
export type CheckInFormValues = z.output<typeof checkInSchema>;

export const loginSchema = z.object({
  email: z.string().trim().email("Enter a valid email."),
  password: z.string().min(1, "Enter your password."),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const signupSchema = z.object({
  display_name: z.string().trim().min(1, "What should we call you?").max(80),
  email: z.string().trim().email("Enter a valid email."),
  password: z.string().min(8, "Use at least 8 characters.").max(128),
});
export type SignupValues = z.infer<typeof signupSchema>;

export const metricSchema = z
  .object({
    name: z.string().trim().min(1, "Give it a name.").max(60),
    min: z.coerce.number({ invalid_type_error: "Enter a number." }),
    max: z.coerce.number({ invalid_type_error: "Enter a number." }),
    unit: z.string().trim().max(20).optional(),
  })
  .refine((v) => v.max > v.min, { message: "Max must be bigger than min.", path: ["max"] });
export type MetricValues = z.infer<typeof metricSchema>;

export const profileSchema = z.object({
  display_name: z.string().trim().min(1, "What should we call you?").max(80),
  timezone: z.string().min(1, "Pick your timezone."),
});
export type ProfileValues = z.infer<typeof profileSchema>;
