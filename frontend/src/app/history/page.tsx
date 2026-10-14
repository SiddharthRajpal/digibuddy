"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PageTitle } from "@/components/ui/Book";
import { Button } from "@/components/ui/Button";
import { EmptyNote, ErrorNote, LoadingNote, TagChip } from "@/components/ui/Controls";
import { PredictionChart, type PredictionPoint } from "@/components/ui/Charts";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth";
import { addDays, formatDay, todayIn } from "@/lib/dates";
import { FEELING_COPY, usesWeather, weatherFor } from "@/lib/feelings";
import { useCheckins, usePredictionHistory } from "@/lib/hooks";
import { TARGETS, type CheckIn, type Forecast, type Target } from "@/types/api";

import styles from "./history.module.css";

function useRange(days: number): { from: string; to: string } {
  const { user } = useAuth();
  const to = todayIn(user?.timezone ?? "UTC");
  return { from: addDays(to, -(days - 1)), to };
}

function Chart() {
  const [target, setTarget] = useState<Target>("mood");
  const { from, to } = useRange(30);
  const history = usePredictionHistory(from, to);
  const points: PredictionPoint[] = useMemo(
    () =>
      [...(history.data?.items ?? [])]
        .sort((a, b) => a.target_date.localeCompare(b.target_date))
        .filter((p) => p.target_date <= to)
        .map((p) => ({
          date: p.target_date,
          predicted: p[target].predicted,
          lower: p[target].lower,
          upper: p[target].upper,
          actual: p[target].actual ?? null,
        })),
    [history.data, target, to],
  );

  return (
    <div className="stack-lg">
      <PageTitle eyebrow="History" title="Guessed vs. felt">
        <p>The last 30 days: my guess and its range, and how you actually felt.</p>
      </PageTitle>
      <div className="row" role="group" aria-label="Which feeling to show">
        {TARGETS.map((t) => (
          <TagChip key={t} label={FEELING_COPY[t].label} selected={t === target} onToggle={() => setTarget(t)} />
        ))}
      </div>
      {history.isPending ? (
        <LoadingNote />
      ) : history.isError ? (
        <ErrorNote message="I couldn't load your history." onRetry={() => history.refetch()} />
      ) : points.length === 0 ? (
        <EmptyNote title="No forecasts yet">After 7 check-ins I start guessing, and they show up here.</EmptyNote>
      ) : (
        <PredictionChart
          points={points}
          title={`${FEELING_COPY[target].label}: forecast and actual, last 30 days`}
          weather={usesWeather(target)}
        />
      )}
    </div>
  );
}

function DayRow({ c, p }: { c: CheckIn; p?: Forecast }) {
  return (
    <li className={styles.day}>
      <div className={styles.dayHead}>
        <span className="t-title-md">{formatDay(c.date)}</span>
        <Link href={`/checkin/${c.date}`} className={styles.edit} aria-label={`Edit ${formatDay(c.date)}`}>
          <Icon name="pencil" size={20} />
        </Link>
      </div>
      <dl className={styles.values}>
        {TARGETS.map((t) => (
          <div key={t} className={styles.value}>
            <dt className="t-caption">{FEELING_COPY[t].label}</dt>
            <dd className="tabular">
              {usesWeather(t) ? <Icon name={weatherFor(c[t]).icon} size={18} /> : null}
              <span className="t-title-md">{c[t]}</span>
              {p ? <span className={styles.guess}>guess {p[t].predicted.toFixed(1)}</span> : null}
            </dd>
          </div>
        ))}
      </dl>
      {c.tags.length > 0 ? <p className={styles.tags}>{c.tags.join(" · ")}</p> : null}
    </li>
  );
}

function DayList() {
  const [days, setDays] = useState(14);
  const { from, to } = useRange(days);
  const checkins = useCheckins(from, to);
  const history = usePredictionHistory(from, to);
  const byDate = useMemo(() => {
    const m = new Map<string, Forecast>();
    history.data?.items.forEach((p) => m.set(p.target_date, p));
    return m;
  }, [history.data]);

  return (
    <div className="stack-lg">
      <header className="stack">
        <p className="eyebrow">Your pages</p>
        <h2 className="t-title-lg">Day by day</h2>
      </header>
      {checkins.isPending ? (
        <LoadingNote />
      ) : checkins.isError ? (
        <ErrorNote message="I couldn't load your pages." onRetry={() => checkins.refetch()} />
      ) : checkins.data.length === 0 ? (
        <EmptyNote title="No pages yet">Your check-ins will be kept here, newest first.</EmptyNote>
      ) : (
        <>
          <ul className={styles.list}>
            {[...checkins.data].reverse().map((c) => (
              <DayRow key={c.date} c={c} p={byDate.get(c.date)} />
            ))}
          </ul>
          <Button variant="secondary" onClick={() => setDays((d) => d + 30)} loading={checkins.isFetching}>
            Show older pages
          </Button>
        </>
      )}
    </div>
  );
}

export default function HistoryPage() {
  return <AppShell label="History" left={<Chart />} right={<DayList />} />;
}
