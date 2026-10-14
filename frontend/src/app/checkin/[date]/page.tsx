"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DetailsFields, FeelingsFields } from "@/components/checkin/CheckInFields";
import { useCheckInForm, type CheckInFormApi } from "@/components/checkin/useCheckInForm";
import { PageTitle, useBook } from "@/components/ui/Book";
import { Button, ButtonLink } from "@/components/ui/Button";
import { ErrorNote, LoadingNote } from "@/components/ui/Controls";
import { CompareNote } from "@/components/ui/ForecastCard";
import { SupportNote } from "@/components/ui/SupportNote";
import { useAuth } from "@/lib/auth";
import { addDays, diffDays, formatDay, todayIn } from "@/lib/dates";
import { useCheckin, useDeleteCheckin, useMetrics } from "@/lib/hooks";
import type { CheckIn, CheckInResult } from "@/types/api";

const FORM_ID = "checkin-form";
const BACKFILL_DAYS = 3;

function SaveRow({ api, editing, date }: { api: CheckInFormApi; editing: boolean; date: string }) {
  const del = useDeleteCheckin();
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="stack">
      {api.error ? <ErrorNote message={api.error} /> : null}
      {Object.keys(api.form.formState.errors).length > 0 ? (
        <p role="alert" style={{ color: "var(--brick)" }}>
          A few answers need another look.
        </p>
      ) : null}
      <div className="row">
        <Button type="submit" form={FORM_ID} loading={api.saving} icon="check">
          {editing ? "Save changes" : "Save this page"}
        </Button>
        {editing ? (
          confirming ? (
            <>
              <Button
                variant="secondary"
                icon="trash"
                loading={del.isPending}
                onClick={async () => {
                  await del.mutateAsync(date);
                  router.push("/history");
                }}
              >
                Yes, remove this page
              </Button>
              <Button variant="quiet" onClick={() => setConfirming(false)}>
                Keep it
              </Button>
            </>
          ) : (
            <Button variant="quiet" icon="trash" onClick={() => setConfirming(true)}>
              Remove this page
            </Button>
          )
        ) : null}
      </div>
    </div>
  );
}

function Saved({ result, date }: { result: CheckInResult; date: string }) {
  const scored = result.scored_prediction;
  return (
    <div className="stack-lg" role="status">
      {result.support ? <SupportNote support={result.support} /> : null}
      <PageTitle eyebrow={formatDay(date)} title="Page saved" />
      {scored?.mood.actual != null ? (
        <CompareNote predicted={scored.mood.predicted} actual={scored.mood.actual} />
      ) : null}
      <div className="row">
        <ButtonLink href="/" variant="primary" iconRight="arrow-right">
          Back to today
        </ButtonLink>
        <ButtonLink href="/history" variant="quiet">
          See your history
        </ButtonLink>
      </div>
    </div>
  );
}

function Editor({ date, existing }: { date: string; existing: CheckIn | null }) {
  const router = useRouter();
  const [result, setResult] = useState<CheckInResult | null>(null);
  const { turn } = useBook();
  const metrics = useMetrics();
  const api = useCheckInForm(date, existing, (r) => {
    if (r) turn("forward", () => setResult(r));
    else router.push("/history");
  });

  if (result) return <AppShell label="Check-in" left={<Saved result={result} date={date} />} />;

  return (
    <AppShell
      label="Check-in"
      left={
        <form id={FORM_ID} onSubmit={api.submit} noValidate className="stack-lg">
          <PageTitle eyebrow={formatDay(date, { weekday: "long" })} title={existing ? "Edit this page" : "How are you feeling?"}>
            <p>Five quick numbers. Everything on the next page is optional.</p>
          </PageTitle>
          <FeelingsFields form={api.form} />
        </form>
      }
      right={
        <div className="stack-lg">
          <header className="stack">
            <p className="eyebrow">Page 2 · optional</p>
            <h2 className="t-title-lg">A few details about your day</h2>
          </header>
          {metrics.isError ? <ErrorNote message="I couldn't load your trackers." /> : null}
          <DetailsFields form={api.form} metrics={metrics.data ?? []} />
          <SaveRow api={api} editing={Boolean(existing)} date={date} />
        </div>
      }
    />
  );
}

export default function CheckInPage() {
  const params = useParams<{ date: string }>();
  const { user } = useAuth();
  const date = params?.date ?? "";
  const checkin = useCheckin(date);

  const today = user ? todayIn(user.timezone) : null;
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(date);

  if (!user || checkin.isPending) {
    return <AppShell label="Check-in" left={<LoadingNote />} />;
  }
  if (!valid) {
    return <AppShell label="Check-in" left={<ErrorNote message="That doesn't look like a date." />} />;
  }
  if (checkin.isError) {
    return (
      <AppShell
        label="Check-in"
        left={<ErrorNote message="I couldn't open this page." onRetry={() => checkin.refetch()} />}
      />
    );
  }
  const age = today ? diffDays(today, date) : 0;
  if (!checkin.data && (age < 0 || age > BACKFILL_DAYS)) {
    return (
      <AppShell
        label="Check-in"
        left={
          <div className="stack">
            <PageTitle eyebrow={formatDay(date)} title={age < 0 ? "Not yet" : "This page is closed"} />
            <p>
              {age < 0
                ? "This day hasn't happened yet. Come back then."
                : `You can fill in the last ${BACKFILL_DAYS} days. Older pages stay as they are.`}
            </p>
            <ButtonLink href={`/checkin/${today}`} variant="primary">
              Check in for today
            </ButtonLink>
            {today ? (
              <ButtonLink href={`/checkin/${addDays(today, -1)}`} variant="quiet">
                Fill in yesterday
              </ButtonLink>
            ) : null}
          </div>
        }
      />
    );
  }
  return <Editor key={date} date={date} existing={checkin.data} />;
}
