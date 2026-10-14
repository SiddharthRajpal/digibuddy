/**
 * API types. Generated from the backend's OpenAPI schema into `openapi.d.ts`
 * (`npm run gen:api` after `python -m scripts.export_openapi` in /backend), and
 * re-exported here with friendly names. Never hand-write API shapes elsewhere.
 */
import type { components } from "./openapi";

type S = components["schemas"];

export type User = S["UserOut"];
export type TokenResponse = S["TokenOut"];
export type SignupBody = S["SignupIn"];
export type LoginBody = S["LoginIn"];
export type UserPatch = S["UserPatch"];

export type CheckIn = S["CheckInOut"];
export type CheckInCreate = S["CheckInCreate"];
export type CheckInPatch = S["CheckInPatch"];
export type CheckInResult = S["CheckInResult"];
export type MetricValue = S["MetricValueIn"];

export type Factor = S["FactorOut"];
export type TargetForecast = S["TargetForecastOut"];
export type Forecast = S["ForecastOut"];
export type Tomorrow = S["TomorrowOut"];
export type Support = S["SupportOut"];
export type SupportResource = S["SupportResourceOut"];
export type PredictionHistory = S["PredictionHistoryOut"];

export type Metric = S["MetricOut"];
export type MetricBody = S["MetricIn"];
export type MetricPatch = S["MetricPatch"];

export type Twin = S["TwinOut"];
export type TargetAccuracy = S["TargetAccuracyOut"];
export type TargetModel = S["TargetModelOut"];
export type AccuracyPoint = S["AccuracyPointOut"];

export type Insight = S["InsightOut"];
export type Insights = S["InsightsOut"];
export type Meta = S["MetaOut"];
export type Export = S["ExportOut"];

export type Target = "mood" | "energy" | "stress";
export const TARGETS: readonly Target[] = ["mood", "energy", "stress"] as const;

export type Feeling = "mood" | "energy" | "stress" | "anxiety" | "focus";
export const FEELINGS: readonly Feeling[] = ["mood", "energy", "stress", "anxiety", "focus"] as const;
