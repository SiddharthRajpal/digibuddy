"use client";

import { useState } from "react";
import { Controller, useWatch, type UseFormReturn } from "react-hook-form";

import { FactorSlot, Section, TagChip } from "@/components/ui/Controls";
import { FeelingScale } from "@/components/ui/FeelingScale";
import { TextArea, TextField } from "@/components/ui/TextField";
import { Button } from "@/components/ui/Button";
import type { CheckInFormInput, CheckInFormValues } from "@/lib/schemas";
import { FEELINGS, type Metric } from "@/types/api";

type Form = UseFormReturn<CheckInFormInput, unknown, CheckInFormValues>;

const SUGGESTED_TAGS = ["exam", "deadline", "travel", "sick", "date", "gym", "family", "friends", "rest day"];

/** Page 1: the five feelings (required). */
export function FeelingsFields({ form }: { form: Form }) {
  const { errors } = form.formState;
  return (
    <div className="stack-lg">
      {FEELINGS.map((f) => (
        <Controller
          key={f}
          control={form.control}
          name={f}
          render={({ field }) => (
            <FeelingScale
              feeling={f}
              value={field.value as number | undefined}
              onChange={field.onChange}
              error={errors[f]?.message}
            />
          )}
        />
      ))}
    </div>
  );
}

function filled(values: unknown[]): boolean {
  return values.some((v) => v !== "" && v !== null && v !== undefined);
}

function TagPicker({ form }: { form: Form }) {
  const [draft, setDraft] = useState("");
  return (
    <Controller
      control={form.control}
      name="tags"
      render={({ field }) => {
        const tags = (field.value ?? []) as string[];
        const toggle = (t: string) =>
          field.onChange(tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]);
        const custom = tags.filter((t) => !SUGGESTED_TAGS.includes(t));
        const add = () => {
          const t = draft.trim().toLowerCase();
          if (t && !tags.includes(t) && t.length <= 32) field.onChange([...tags, t]);
          setDraft("");
        };
        return (
          <div className="stack">
            <div className="row" role="group" aria-label="Tags for today">
              {SUGGESTED_TAGS.map((t) => (
                <TagChip key={t} label={t} selected={tags.includes(t)} onToggle={() => toggle(t)} />
              ))}
              {custom.map((t) => (
                <TagChip key={t} label={t} onRemove={() => toggle(t)} />
              ))}
            </div>
            <div className="row">
              <div style={{ flex: 1, minWidth: 160 }}>
                <TextField
                  label="Add your own tag"
                  value={draft}
                  maxLength={32}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      add();
                    }
                  }}
                />
              </div>
              <Button variant="secondary" icon="plus" onClick={add} style={{ alignSelf: "flex-end" }}>
                Add
              </Button>
            </div>
            {form.formState.errors.tags ? (
              <p role="alert" style={{ color: "var(--brick)" }}>
                {form.formState.errors.tags.message}
              </p>
            ) : null}
          </div>
        );
      }}
    />
  );
}

/** Page 2: optional details in collapsible sections. */
export function DetailsFields({ form, metrics }: { form: Form; metrics: Metric[] }) {
  const { register, formState } = form;
  const e = formState.errors;
  const v = useWatch({ control: form.control });
  const num = { inputMode: "decimal" as const, type: "number", step: "any" };
  const int = { inputMode: "numeric" as const, type: "number", step: 1 };

  return (
    <div className="stack">
      <Section title="Sleep" icon="sleep" summary="optional">
        <FactorSlot icon="moon" title="Last night" filled={filled([v.sleep_hours, v.sleep_quality])}>
          <TextField label="Hours slept" suffix="h" {...num} min={0} max={24} error={e.sleep_hours?.message} {...register("sleep_hours")} />
          <TextField label="Sleep quality (1–5)" {...int} min={1} max={5} error={e.sleep_quality?.message} {...register("sleep_quality")} />
        </FactorSlot>
      </Section>

      <Section title="Activity" icon="shoe" summary="optional">
        <FactorSlot icon="shoe" title="Moving and outside" filled={filled([v.exercise_minutes, v.outdoor_minutes])}>
          <TextField label="Exercise" suffix="min" {...int} min={0} error={e.exercise_minutes?.message} {...register("exercise_minutes")} />
          <TextField label="Outdoors" suffix="min" {...int} min={0} error={e.outdoor_minutes?.message} {...register("outdoor_minutes")} />
        </FactorSlot>
      </Section>

      <Section title="Lifestyle" icon="cup" summary="optional">
        <FactorSlot
          icon="cup"
          title="Screens, drinks and meals"
          filled={filled([v.screen_time_hours, v.caffeine_servings, v.alcohol_units, v.meals_eaten])}
        >
          <TextField label="Screen time" suffix="h" {...num} min={0} max={24} error={e.screen_time_hours?.message} {...register("screen_time_hours")} />
          <TextField label="Caffeine" suffix="cups" {...int} min={0} error={e.caffeine_servings?.message} {...register("caffeine_servings")} />
          <TextField label="Alcohol" suffix="units" {...int} min={0} error={e.alcohol_units?.message} {...register("alcohol_units")} />
          <TextField label="Meals (0–5)" {...int} min={0} max={5} error={e.meals_eaten?.message} {...register("meals_eaten")} />
        </FactorSlot>
      </Section>

      <Section title="People and load" icon="people" summary="optional">
        <FactorSlot icon="people" title="Your day" filled={filled([v.social_interaction, v.workload])}>
          <TextField label="Time with people (1–5)" {...int} min={1} max={5} error={e.social_interaction?.message} {...register("social_interaction")} />
          <TextField label="Workload (1–5)" {...int} min={1} max={5} error={e.workload?.message} {...register("workload")} />
        </FactorSlot>
      </Section>

      <Section title="Tags" icon="tag" summary="what kind of day">
        <TagPicker form={form} />
      </Section>

      {metrics.length > 0 ? (
        <Section title="Your trackers" icon="ruler" summary="optional">
          <FactorSlot icon="ruler" title="Your own numbers" filled={filled(Object.values(v.custom_metrics ?? {}))}>
            {metrics.map((m) => (
              <TextField
                key={m.id}
                label={`${m.name} (${m.min}–${m.max})`}
                suffix={m.unit ?? undefined}
                {...num}
                min={m.min}
                max={m.max}
                {...register(`custom_metrics.${m.id}` as const)}
              />
            ))}
          </FactorSlot>
        </Section>
      ) : null}

      <Section title="Notes" icon="lock" summary="private, never analysed">
        <TextArea
          label="Anything you want to remember"
          hint="Only you see this. DigiBuddy never reads notes to make forecasts."
          rows={4}
          maxLength={2000}
          error={e.notes?.message}
          {...register("notes")}
        />
      </Section>
    </div>
  );
}
