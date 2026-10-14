"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";

import { AppShell } from "@/components/AppShell";
import { MetricsEditor } from "@/components/MetricsEditor";
import { PageTitle } from "@/components/ui/Book";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Section, Toggle } from "@/components/ui/Controls";
import { StickyNote } from "@/components/ui/Paper";
import { SelectField, TextField } from "@/components/ui/TextField";
import { useAuth } from "@/lib/auth";
import { allTimeZones } from "@/lib/dates";
import { useDeleteAccount, useExport, useMeta, useUpdateMe } from "@/lib/hooks";
import { profileSchema, type ProfileValues } from "@/lib/schemas";
import { useTheme } from "@/lib/theme";

function Profile() {
  const { user } = useAuth();
  const update = useUpdateMe();
  const [saved, setSaved] = useState(false);
  const zones = useMemo(() => allTimeZones().map((z) => ({ value: z, label: z.replace(/_/g, " ") })), []);
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    values: { display_name: user?.display_name ?? "", timezone: user?.timezone ?? "UTC" },
  });
  const e = form.formState.errors;
  const onSubmit = form.handleSubmit(async (v) => {
    setSaved(false);
    await update.mutateAsync(v);
    setSaved(true);
  });
  return (
    <form onSubmit={onSubmit} noValidate className="stack" aria-label="Profile">
      <TextField label="What should I call you?" autoComplete="nickname" error={e.display_name?.message} {...form.register("display_name")} />
      <SelectField
        label="Your timezone"
        hint="Your days start and end at midnight here."
        options={zones.some((z) => z.value === user?.timezone) ? zones : [{ value: user?.timezone ?? "UTC", label: user?.timezone ?? "UTC" }, ...zones]}
        error={e.timezone?.message}
        {...form.register("timezone")}
      />
      {update.error ? <ErrorNote message={update.error.message} /> : null}
      {saved ? <p role="status">Saved.</p> : null}
      <div>
        <Button type="submit" loading={update.isPending}>
          Save profile
        </Button>
      </div>
    </form>
  );
}

function Theme() {
  const [theme, setTheme] = useTheme();
  return (
    <div className="stack">
      <Toggle
        label="Lamplight"
        hint="A darker book for reading at night."
        checked={theme === "lamplight"}
        onChange={(e) => setTheme(e.target.checked ? "lamplight" : "daylight")}
      />
      <Toggle
        label="Match my device"
        hint="Follow your device's light or dark setting."
        checked={theme === "system"}
        onChange={(e) => setTheme(e.target.checked ? "system" : "daylight")}
      />
    </div>
  );
}

function DataControls() {
  const exp = useExport();
  const del = useDeleteAccount();
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const [asking, setAsking] = useState(false);
  return (
    <div className="stack-lg">
      <section className="stack" aria-labelledby="export-title">
        <h3 id="export-title" className="t-title-md">
          Take your pages with you
        </h3>
        <p className="soft">Download everything as JSON, or just your check-ins as a spreadsheet (CSV).</p>
        <div className="row">
          <Button variant="secondary" icon="download" onClick={() => exp.mutate("json")} loading={exp.isPending && exp.variables === "json"}>
            All data (JSON)
          </Button>
          <Button variant="secondary" icon="download" onClick={() => exp.mutate("csv")} loading={exp.isPending && exp.variables === "csv"}>
            Check-ins (CSV)
          </Button>
        </div>
        {exp.error ? <ErrorNote message={exp.error.message} /> : null}
      </section>

      <section className="stack" aria-labelledby="delete-title">
        <h3 id="delete-title" className="t-title-md">
          Close the book for good
        </h3>
        <p className="soft">
          This deletes your account, every check-in, forecast and everything your twin learned.
          It can&apos;t be undone.
        </p>
        {!asking ? (
          <div>
            <Button variant="secondary" icon="trash" onClick={() => setAsking(true)}>
              Delete my account
            </Button>
          </div>
        ) : (
          <form
            className="stack"
            onSubmit={async (e) => {
              e.preventDefault();
              await del.mutateAsync();
              router.replace("/signup");
            }}
          >
            <TextField
              label='Type "delete" to confirm'
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="off"
            />
            <div className="row">
              <Button type="submit" variant="secondary" icon="trash" disabled={confirm.trim().toLowerCase() !== "delete"} loading={del.isPending}>
                Delete everything
              </Button>
              <Button variant="quiet" onClick={() => { setAsking(false); setConfirm(""); }}>
                Keep my book
              </Button>
            </div>
            {del.error ? <ErrorNote message={del.error.message} /> : null}
          </form>
        )}
      </section>
    </div>
  );
}

function Left() {
  const { logout } = useAuth();
  const router = useRouter();
  return (
    <div className="stack-lg">
      <PageTitle eyebrow="Settings" title="Your book" />
      <Section title="Profile" icon="people" defaultOpen>
        <Profile />
      </Section>
      <Section title="Reading light" icon="moon" defaultOpen>
        <Theme />
      </Section>
      <Section title="Your trackers" icon="ruler">
        <MetricsEditor />
      </Section>
      <div>
        <Button
          variant="quiet"
          iconRight="arrow-right"
          onClick={async () => {
            await logout();
            router.replace("/login");
          }}
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}

function Right() {
  const meta = useMeta();
  return (
    <div className="stack-lg">
      <header className="stack">
        <p className="eyebrow">Privacy</p>
        <h2 className="t-title-lg">Your pages are yours</h2>
      </header>
      <DataControls />
      <StickyNote tone="paper" tilt={1}>
        <p className="t-label">About DigiBuddy</p>
        <p className="t-body-sm">{meta.data?.disclaimer ?? "DigiBuddy is a self-reflection tool, not a medical device."}</p>
        {meta.data ? <p className="t-caption soft">Version {meta.data.version}</p> : null}
      </StickyNote>
    </div>
  );
}

export default function SettingsPage() {
  return <AppShell label="Settings" left={<Left />} right={<Right />} />;
}
