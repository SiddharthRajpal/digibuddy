"use client";

import { AppShell } from "@/components/AppShell";
import { PageTitle } from "@/components/ui/Book";
import { ButtonLink } from "@/components/ui/Button";
import { AccuracyChart, TwinMeter } from "@/components/ui/Charts";
import { EmptyNote, ErrorNote, LoadingNote } from "@/components/ui/Controls";
import { Quokka } from "@/components/ui/Quokka";
import { FEELING_COPY } from "@/lib/feelings";
import { useTwin } from "@/lib/hooks";
import { TARGETS, type Twin } from "@/types/api";

import styles from "./twin.module.css";

const STAGES: Record<number, { title: string; body: string }> = {
  0: { title: "Getting to know you", body: "I'm collecting your first week of pages." },
  1: { title: "Learning your rhythm", body: "I follow your recent days and how each weekday tends to go." },
  2: { title: "Learning your patterns", body: "I look at how sleep, activity and your days shape tomorrow." },
  3: { title: "Reading you closely", body: "I try a few ways of reading you and keep whichever works best." },
};

const MODEL_WORDS: Record<string, string> = {
  naive: "same as today (my starting point)",
  baseline: "your recent trend and weekday rhythm",
  ridge: "your personal patterns (a simple weighted model)",
  gbm: "your personal patterns (a pattern-finding model)",
};

function pct(v: number | null | undefined): string {
  return v == null ? "–" : `${Math.round(v * 100)}%`;
}

function num(v: number | null | undefined): string {
  return v == null ? "–" : v.toFixed(2);
}

function Left({ twin }: { twin: Twin }) {
  const stage = STAGES[twin.stage] ?? STAGES[0]!;
  const learning = twin.in_tune_pct != null ? "I'm learning!" : "Give me a week of pages.";
  return (
    <div className="stack-lg">
      <PageTitle eyebrow={`Chapter ${twin.stage + 1} of 4`} title={stage.title}>
        <p>{stage.body}</p>
      </PageTitle>
      <div className={styles.meterRow}>
        <TwinMeter percent={twin.in_tune_pct ?? null} label={`${twin.in_tune_pct ?? 0}% in tune with you`} />
        <Quokka says={learning} size={96} />
      </div>
      <p className="soft">
        &ldquo;In tune&rdquo; means my guess was within 1 point of how you felt, over the last 30 days.
      </p>
      <dl className={styles.facts}>
        <div>
          <dt className="t-caption">Pages written</dt>
          <dd className="t-title-lg tabular">{twin.days_logged}</dd>
        </div>
        <div>
          <dt className="t-caption">Next chapter in</dt>
          <dd className="t-title-lg tabular">
            {twin.days_to_next_stage == null ? "–" : `${twin.days_to_next_stage} pages`}
          </dd>
        </div>
        <div>
          <dt className="t-caption">Last studied your pages</dt>
          <dd className="t-body-sm">
            {twin.last_trained_at
              ? new Date(twin.last_trained_at).toLocaleString("en-GB", {
                  day: "numeric",
                  month: "short",
                  hour: "numeric",
                  minute: "2-digit",
                })
              : "not yet"}
          </dd>
        </div>
      </dl>
      <ButtonLink href="/insights" iconRight="arrow-right">
        What moves your days
      </ButtonLink>
    </div>
  );
}

function Right({ twin }: { twin: Twin }) {
  const points = twin.series.map((p) => ({ date: p.date, twin: p.mae_7d ?? null, naive: p.naive_mae_7d ?? null }));
  return (
    <div className="stack-lg">
      <header className="stack">
        <p className="eyebrow">Getting smarter</p>
        <h2 className="t-title-lg">How close my guesses have been</h2>
      </header>
      {points.length > 1 ? (
        <AccuracyChart points={points} title="Average points off over 7 days, compared with guessing the same as today" />
      ) : (
        <EmptyNote title="Nothing to compare yet">Once I’ve made a few guesses, you’ll see them get closer here.</EmptyNote>
      )}
      <table className={styles.table}>
        <caption className="t-title-md">By feeling, last 30 days</caption>
        <thead>
          <tr>
            <th scope="col">Feeling</th>
            <th scope="col">Off by (7 / 30 days)</th>
            <th scope="col">Within 1 point</th>
            <th scope="col">Better than &ldquo;same as today&rdquo;</th>
            <th scope="col">Inside my range</th>
          </tr>
        </thead>
        <tbody>
          {TARGETS.map((t) => {
            const a = twin.accuracy[t];
            return (
              <tr key={t}>
                <th scope="row">{FEELING_COPY[t].label}</th>
                <td className="tabular">
                  {num(a?.mae_7d)} / {num(a?.mae_30d)}
                </td>
                <td className="tabular">{pct(a?.within_1_rate)}</td>
                <td className="tabular">
                  {a?.improvement_vs_naive_pct == null ? "–" : `${a.improvement_vs_naive_pct}%`}
                </td>
                <td className="tabular">{pct(a?.interval_coverage)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <section className="stack" aria-labelledby="how-title">
        <h3 id="how-title" className="t-title-md">
          How I read each feeling right now
        </h3>
        <ul className={styles.models}>
          {TARGETS.map((t) => {
            const m = twin.models[t];
            return (
              <li key={t}>
                <span className="t-label">{FEELING_COPY[t].label}:</span>{" "}
                {m?.model_type ? MODEL_WORDS[m.model_type] ?? m.model_type : "not yet"}
              </li>
            );
          })}
        </ul>
        <p className="t-body-sm soft">
          I only switch to a new way of reading you when it beats both my current one and simply
          guessing &ldquo;same as today&rdquo; on your recent days.
        </p>
      </section>
    </div>
  );
}

export default function TwinPage() {
  const twin = useTwin();
  if (twin.isPending) return <AppShell label="Your twin" left={<LoadingNote />} />;
  if (twin.isError)
    return (
      <AppShell
        label="Your twin"
        left={<ErrorNote message="I couldn't load your twin." onRetry={() => twin.refetch()} />}
      />
    );
  return <AppShell label="Your twin" left={<Left twin={twin.data} />} right={<Right twin={twin.data} />} />;
}
