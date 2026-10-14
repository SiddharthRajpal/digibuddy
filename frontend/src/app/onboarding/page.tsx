"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { MetricsEditor } from "@/components/MetricsEditor";
import { PageTitle, useBook } from "@/components/ui/Book";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Controls";
import { StickyNote } from "@/components/ui/Paper";
import { Quokka } from "@/components/ui/Quokka";
import { SelectField } from "@/components/ui/TextField";
import { useAuth } from "@/lib/auth";
import { allTimeZones, browserTimeZone } from "@/lib/dates";
import { useMeta, useUpdateMe } from "@/lib/hooks";

import styles from "./onboarding.module.css";

/** Three pages, one idea each: how it works, the promise (not a medical device), your setup. */
export default function OnboardingPage() {
  const [step, setStep] = useState(0);
  const { turn } = useBook();
  // Each step is a page of the book: moving between them turns the page.
  const goTo = (n: number) => turn(n > step ? "forward" : "back", () => setStep(n));
  const { user } = useAuth();
  const meta = useMeta();
  const update = useUpdateMe();
  const router = useRouter();
  const [timezone, setTimezone] = useState("UTC");
  const [agreed, setAgreed] = useState(false);
  const zones = useMemo(() => allTimeZones().map((z) => ({ value: z, label: z.replace(/_/g, " ") })), []);

  useEffect(() => setTimezone(browserTimeZone()), []);
  useEffect(() => {
    if (user?.onboarding_completed) router.replace("/");
  }, [user, router]);

  const finish = async () => {
    await update.mutateAsync({ timezone, onboarding_completed: true });
    router.replace("/");
  };

  const pages = [
    <div key="how" className="stack-lg">
      <PageTitle eyebrow="Page 1 of 3" title={`Hello, ${user?.display_name ?? "friend"}`}>
        <p>This is your book. One check-in is one page, and it takes under a minute.</p>
      </PageTitle>
      <Quokka says="I'll keep you company." large size={160} />
      <ol className={styles.steps}>
        <li>
          <span className="t-title-md">Write a page</span> How you feel, and a few things about your day.
        </li>
        <li>
          <span className="t-title-md">A week becomes a forecast</span> After 7 pages I start guessing how tomorrow might feel.
        </li>
        <li>
          <span className="t-title-md">I get better at reading you</span> Each evening I compare my guess with your page and learn from the gap.
        </li>
      </ol>
      <Button iconRight="arrow-right" onClick={() => goTo(1)}>
        Next
      </Button>
    </div>,

    <div key="promise" className="stack-lg">
      <PageTitle eyebrow="Page 2 of 3" title="A promise, before we start" />
      <StickyNote tone="petal" tape>
        <p>
          {meta.data?.disclaimer ??
            "DigiBuddy is a self-reflection tool, not a medical device. Its forecasts are estimates, not advice."}
        </p>
      </StickyNote>
      <p>
        Your notes stay private: they are never read to make forecasts. You can download or
        delete everything at any time.
      </p>
      <label className={styles.agree}>
        <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
        <span>I understand DigiBuddy is for reflection, not medical advice.</span>
      </label>
      <div className="row">
        <Button variant="quiet" icon="arrow-left" onClick={() => goTo(0)}>
          Back
        </Button>
        <Button iconRight="arrow-right" disabled={!agreed} onClick={() => goTo(2)}>
          Next
        </Button>
      </div>
    </div>,

    <div key="setup" className="stack-lg">
      <PageTitle eyebrow="Page 3 of 3" title="Set up your book">
        <p>Your days start and end at midnight in your timezone.</p>
      </PageTitle>
      <SelectField
        label="Your timezone"
        value={timezone}
        onChange={(e) => setTimezone(e.target.value)}
        options={zones.some((z) => z.value === timezone) ? zones : [{ value: timezone, label: timezone }, ...zones]}
      />
      <section className="stack" aria-labelledby="trackers-title">
        <h2 id="trackers-title" className="t-title-md">
          Anything else you’d like to track? (optional)
        </h2>
        <MetricsEditor />
      </section>
      {update.error ? <ErrorNote message={update.error.message} /> : null}
      <div className="row">
        <Button variant="quiet" icon="arrow-left" onClick={() => goTo(1)}>
          Back
        </Button>
        <Button iconRight="arrow-right" loading={update.isPending} onClick={finish}>
          Open my book
        </Button>
      </div>
    </div>,
  ];

  return <AppShell label="Welcome" left={pages[step]} />;
}
