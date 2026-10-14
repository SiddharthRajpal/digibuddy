"use client";

import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { FeelingsFields } from "@/components/checkin/CheckInFields";
import { useCheckInForm } from "@/components/checkin/useCheckInForm";
import { PageTitle } from "@/components/ui/Book";
import { Button, ButtonLink } from "@/components/ui/Button";
import { EmptyNote, ErrorNote, LoadingNote } from "@/components/ui/Controls";
import { CompareNote, ForecastCard } from "@/components/ui/ForecastCard";
import { Icon } from "@/components/ui/Icon";
import { StickyNote } from "@/components/ui/Paper";
import { Quokka } from "@/components/ui/Quokka";
import { SupportNote } from "@/components/ui/SupportNote";
import { useAuth } from "@/lib/auth";
import { formatDay, greeting, todayIn } from "@/lib/dates";
import { FEELING_COPY, fillFor, usesWeather } from "@/lib/feelings";
import { useCheckin, usePredictionHistory, useTomorrow, useTwin } from "@/lib/hooks";
import type { CheckIn, Tomorrow } from "@/types/api";
import { FEELINGS } from "@/types/api";

import styles from "./today.module.css";

function TodayForm({ date }: { date: string }) {
  const [saved, setSaved] = useState(false);
  const { form, submit, saving, error } = useCheckInForm(date, null, () => setSaved(true));
  return (
    <form onSubmit={submit} className="stack-lg" noValidate aria-label="Today's check-in">
      <FeelingsFields form={form} />
      {error ? <ErrorNote message={error} /> : null}
      {saved ? <p role="status">Saved. Thank you for today’s page.</p> : null}
      <div className="row">
        <Button type="submit" loading={saving} icon="check">
          Check in for today
        </Button>
        <ButtonLink href={`/checkin/${date}`} variant="quiet">
          Add sleep, activity and more
        </ButtonLink>
      </div>
    </form>
  );
}

function TodaySummary({ checkin }: { checkin: CheckIn }) {
  return (
    <ul className={styles.summary} aria-label="Today's feelings">
      {FEELINGS.map((f) => (
        <li
          key={f}
          className={styles.summaryItem}
          style={{
            background: fillFor(f, checkin[f]),
            color: usesWeather(f) ? "var(--on-weather)" : "var(--ink)",
          }}
        >
          <span className="t-label">{FEELING_COPY[f].label}</span>
          <span className="t-title-lg tabular">{checkin[f]}</span>
        </li>
      ))}
    </ul>
  );
}

function Collecting({ data }: { data: Tomorrow }) {
  const slots = Array.from({ length: 7 }, (_, i) => i < data.days_logged);
  return (
    <section className="stack" aria-labelledby="collecting-title">
      <p className="eyebrow">Your first forecast</p>
      <h2 id="collecting-title" className="t-title-lg">
        {data.days_needed} more check-in{data.days_needed === 1 ? "" : "s"} to your first forecast
      </h2>
      <p className="soft">A week of pages becomes a forecast. After that, the book gets better at reading you.</p>
      <ol className={styles.slots} aria-label={`${data.days_logged} of 7 pages written`}>
        {slots.map((done, i) => (
          <li key={i} className={[styles.slot, done ? styles.slotDone : ""].join(" ")}>
            {done ? <Icon name="check" label={`Page ${i + 1} written`} /> : <span className="t-label">{i + 1}</span>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function TomorrowPanel() {
  const tomorrow = useTomorrow();
  const twin = useTwin();
  if (tomorrow.isPending) return <LoadingNote label="Reading the clouds…" />;
  if (tomorrow.isError)
    return <ErrorNote message="I couldn't load tomorrow's forecast." onRetry={() => tomorrow.refetch()} />;
  const data = tomorrow.data;
  if (data.status === "collecting") return <Collecting data={data} />;
  if (!data.forecast)
    return <EmptyNote title="No forecast yet">Check in today and I’ll make one.</EmptyNote>;
  return (
    <div className="stack-lg">
      <ForecastCard forecast={data.forecast} />
      {twin.data?.in_tune_pct != null ? (
        <StickyNote tone="sprout" tilt={-1.5}>
          <p className="t-note">{twin.data.in_tune_pct}% in tune with you</p>
          <ButtonLink href="/twin" variant="quiet" iconRight="arrow-right">
            See how I’m learning
          </ButtonLink>
        </StickyNote>
      ) : null}
    </div>
  );
}

function TodayLeft() {
  const { user } = useAuth();
  const tz = user?.timezone ?? "UTC";
  const today = todayIn(tz);
  const checkin = useCheckin(today);
  const tomorrow = useTomorrow();
  const scored = usePredictionHistory(today, today);
  const todaysForecast = scored.data?.items[0];
  const support = tomorrow.data?.support;

  return (
    <>
      {support ? <SupportNote support={support} /> : null}
      <PageTitle eyebrow={formatDay(today, { weekday: "long" })} title={`${greeting(tz)}, ${user?.display_name}`} />
      {checkin.isPending ? (
        <LoadingNote />
      ) : checkin.isError ? (
        <ErrorNote message="I couldn't open today's page." onRetry={() => checkin.refetch()} />
      ) : checkin.data ? (
        <div className="stack-lg">
          <Quokka says="Thanks for today's page!" />
          <TodaySummary checkin={checkin.data} />
          {todaysForecast?.mood.actual != null ? (
            <CompareNote predicted={todaysForecast.mood.predicted} actual={todaysForecast.mood.actual} />
          ) : null}
          <ButtonLink href={`/checkin/${today}`} icon="pencil">
            Edit today’s page
          </ButtonLink>
        </div>
      ) : (
        <div className="stack-lg">
          <Quokka says="Ready for today's page? It takes under a minute." />
          <TodayForm date={today} />
        </div>
      )}
    </>
  );
}

export default function TodayPage() {
  return <AppShell label="Today" left={<TodayLeft />} right={<TomorrowPanel />} />;
}
