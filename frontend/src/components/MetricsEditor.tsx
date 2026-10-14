"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { EmptyNote, ErrorNote, LoadingNote } from "@/components/ui/Controls";
import { TextField } from "@/components/ui/TextField";
import { useCreateMetric, useDeleteMetric, useMetrics } from "@/lib/hooks";
import { metricSchema, type MetricValues } from "@/lib/schemas";

import styles from "./MetricsEditor.module.css";

/** Create and remove the user's own numeric trackers ("practice hours"). */
export function MetricsEditor() {
  const metrics = useMetrics();
  const create = useCreateMetric();
  const remove = useDeleteMetric();
  const form = useForm<MetricValues>({
    resolver: zodResolver(metricSchema),
    defaultValues: { name: "", min: 0, max: 10, unit: "" },
  });
  const e = form.formState.errors;

  const onSubmit = form.handleSubmit(async (v) => {
    await create.mutateAsync({ name: v.name, min: v.min, max: v.max, unit: v.unit || null });
    form.reset({ name: "", min: 0, max: 10, unit: "" });
  });

  return (
    <div className="stack">
      {metrics.isPending ? (
        <LoadingNote />
      ) : metrics.isError ? (
        <ErrorNote message="I couldn't load your trackers." onRetry={() => metrics.refetch()} />
      ) : metrics.data.length === 0 ? (
        <EmptyNote title="No trackers yet">Add a number you’d like to follow, like practice hours.</EmptyNote>
      ) : (
        <ul className={styles.list}>
          {metrics.data.map((m) => (
            <li key={m.id} className={styles.item}>
              <span>
                <span className="t-label">{m.name}</span>{" "}
                <span className="soft">
                  {m.min}–{m.max} {m.unit ?? ""}
                </span>
              </span>
              <Button variant="quiet" icon="trash" onClick={() => remove.mutate(m.id)} aria-label={`Remove ${m.name}`}>
                Remove
              </Button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={onSubmit} noValidate className={styles.form} aria-label="Add a tracker">
        <TextField label="Name" placeholder="Practice hours" error={e.name?.message} {...form.register("name")} />
        <TextField label="Lowest" type="number" step="any" error={e.min?.message} {...form.register("min")} />
        <TextField label="Highest" type="number" step="any" error={e.max?.message} {...form.register("max")} />
        <TextField label="Unit" placeholder="hours" error={e.unit?.message} {...form.register("unit")} />
        <div className={styles.submit}>
          <Button type="submit" variant="secondary" icon="plus" loading={create.isPending}>
            Add tracker
          </Button>
        </div>
      </form>
      {create.error ? <ErrorNote message={create.error.message} /> : null}
    </div>
  );
}
