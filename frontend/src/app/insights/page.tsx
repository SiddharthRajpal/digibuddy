"use client";

import { AppShell } from "@/components/AppShell";
import { PageTitle } from "@/components/ui/Book";
import { EmptyNote, ErrorNote, LoadingNote } from "@/components/ui/Controls";
import { Icon } from "@/components/ui/Icon";
import { Polaroid, ReasonNote, tiltFor } from "@/components/ui/Paper";
import { Quokka } from "@/components/ui/Quokka";
import { useInsights } from "@/lib/hooks";
import type { Insight } from "@/types/api";

import styles from "./insights.module.css";

function WeekdayPolaroids({ items }: { items: Insight[] }) {
  if (items.length === 0) return null;
  return (
    <section className="stack" aria-labelledby="weekdays-title">
      <h2 id="weekdays-title" className="t-title-lg">
        Your week
      </h2>
      <div className={styles.polaroids}>
        {items.map((i) => (
          <Polaroid key={i.factor} tilt={tiltFor(i.factor)} caption={i.direction === "higher" ? `brightest: ${i.note}` : `heaviest: ${i.note}`}>
            <Icon name={i.direction === "higher" ? "sun" : "cloud"} size={48} />
          </Polaroid>
        ))}
      </div>
      <ul className="stack">
        {items.map((i) => (
          <li key={i.factor}>{i.text}</li>
        ))}
      </ul>
    </section>
  );
}

function NoteList({ title, items }: { title: string; items: Insight[] }) {
  if (items.length === 0) return null;
  return (
    <section className="stack" aria-label={title}>
      <h2 className="t-title-lg">{title}</h2>
      <ul className={styles.notes}>
        {items.map((i) => (
          <ReasonNote key={i.kind + i.factor} note={i.note} direction={i.direction} detail={i.text} tilt={tiltFor(i.factor)} />
        ))}
      </ul>
    </section>
  );
}

export default function InsightsPage() {
  const insights = useInsights();

  const intro = (
    <PageTitle eyebrow="Insights" title="What moves your days">
      <p>
        Patterns in your own pages. They are observations, not causes, and each one shows how
        many days it is based on.
      </p>
    </PageTitle>
  );

  if (insights.isPending) return <AppShell label="Insights" left={<>{intro}<LoadingNote /></>} />;
  if (insights.isError)
    return (
      <AppShell
        label="Insights"
        left={
          <>
            {intro}
            <ErrorNote message="I couldn't load your insights." onRetry={() => insights.refetch()} />
          </>
        }
      />
    );

  const items = insights.data.items;
  const correlations = items.filter((i) => i.kind === "correlation");
  const tags = items.filter((i) => i.kind === "tag");
  const weekdays = items.filter((i) => i.kind === "weekday");

  if (items.length === 0) {
    return (
      <AppShell
        label="Insights"
        left={
          <>
            {intro}
            <Quokka says="I'm still reading." />
            <EmptyNote title="No clear patterns yet">{insights.data.message}</EmptyNote>
          </>
        }
      />
    );
  }

  return (
    <AppShell
      label="Insights"
      left={
        <>
          {intro}
          <NoteList title="The day after…" items={correlations} />
        </>
      }
      right={
        <>
          <WeekdayPolaroids items={weekdays} />
          <NoteList title="Tags that stand out" items={tags} />
        </>
      }
    />
  );
}
