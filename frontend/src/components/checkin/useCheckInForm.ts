"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";

import { useCreateCheckin, useUpdateCheckin } from "@/lib/hooks";
import { checkInSchema, type CheckInFormInput, type CheckInFormValues } from "@/lib/schemas";
import type { CheckIn, CheckInCreate, CheckInResult } from "@/types/api";

const OPTIONAL_KEYS = [
  "sleep_hours",
  "sleep_quality",
  "exercise_minutes",
  "outdoor_minutes",
  "screen_time_hours",
  "caffeine_servings",
  "alcohol_units",
  "meals_eaten",
  "social_interaction",
  "workload",
] as const;

export type OptionalKey = (typeof OPTIONAL_KEYS)[number];

export function defaultsFrom(existing: CheckIn | null | undefined): CheckInFormInput {
  const custom: Record<string, string> = {};
  existing?.custom_metrics?.forEach((m) => {
    custom[String(m.metric_id)] = String(m.value);
  });
  const optional = Object.fromEntries(
    OPTIONAL_KEYS.map((k) => [k, existing?.[k] ?? ""]),
  ) as Record<OptionalKey, number | string>;
  return {
    mood: existing?.mood as number,
    energy: existing?.energy as number,
    stress: existing?.stress as number,
    anxiety: existing?.anxiety as number,
    focus: existing?.focus as number,
    ...optional,
    tags: existing?.tags ?? [],
    notes: existing?.notes ?? "",
    custom_metrics: custom,
  };
}

export function toPayload(date: string, v: CheckInFormValues): CheckInCreate {
  const custom_metrics = Object.entries(v.custom_metrics)
    .filter(([, val]) => val !== null && val !== undefined)
    .map(([id, val]) => ({ metric_id: Number(id), value: val as number }));
  const optional = Object.fromEntries(OPTIONAL_KEYS.map((k) => [k, v[k] ?? null]));
  return {
    date,
    mood: v.mood,
    energy: v.energy,
    stress: v.stress,
    anxiety: v.anxiety,
    focus: v.focus,
    ...optional,
    tags: v.tags,
    notes: v.notes ? v.notes : null,
    custom_metrics,
  };
}

export interface CheckInFormApi {
  form: UseFormReturn<CheckInFormInput, unknown, CheckInFormValues>;
  submit: (e?: React.BaseSyntheticEvent) => Promise<void>;
  saving: boolean;
  error: string | null;
}

/**
 * All check-in form state and submission. New days are created (POST, which also
 * scores yesterday's forecast); existing days are edited (PATCH).
 */
export function useCheckInForm(
  date: string,
  existing: CheckIn | null | undefined,
  onSaved: (result: CheckInResult | null) => void,
): CheckInFormApi {
  const form = useForm<CheckInFormInput, unknown, CheckInFormValues>({
    resolver: zodResolver(checkInSchema),
    defaultValues: defaultsFrom(existing),
    mode: "onSubmit",
  });
  const create = useCreateCheckin();
  const update = useUpdateCheckin(date);

  useEffect(() => {
    form.reset(defaultsFrom(existing));
  }, [existing, form]);

  const submit = form.handleSubmit(async (values) => {
    const body = toPayload(date, values);
    if (existing) {
      const { date: _ignored, ...patch } = body;
      void _ignored;
      await update.mutateAsync(patch);
      onSaved(null);
    } else {
      onSaved(await create.mutateAsync(body));
    }
  });

  const err = create.error ?? update.error;
  return {
    form,
    submit,
    saving: create.isPending || update.isPending,
    error: err ? err.message : null,
  };
}
