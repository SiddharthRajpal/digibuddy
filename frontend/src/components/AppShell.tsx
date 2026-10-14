"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { Book, type Chapter } from "@/components/ui/Book";
import { LoadingNote } from "@/components/ui/Controls";
import { useAuth } from "@/lib/auth";
import { todayIn } from "@/lib/dates";

function chaptersFor(timeZone: string): Chapter[] {
  return [
    { href: "/", label: "Today", match: "/" },
    { href: `/checkin/${todayIn(timeZone)}`, label: "Check-in", match: "/checkin" },
    { href: "/history", label: "History", match: "/history" },
    { href: "/twin", label: "Your twin", match: "/twin" },
    { href: "/insights", label: "Insights", match: "/insights" },
    { href: "/settings", label: "Settings", match: "/settings" },
  ];
}

export interface AppShellProps {
  label: string;
  left: ReactNode;
  right?: ReactNode;
  /** Show chapter tabs (signed-in chapters). */
  chapters?: boolean;
}

/** Signed-in pages: redirects to sign in or onboarding as needed, then shows the book. */
export function AppShell({ label, left, right, chapters = true }: AppShellProps) {
  const { status, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname ?? "/")}`);
    else if (status === "authenticated" && user && !user.onboarding_completed && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [status, user, router, pathname]);

  if (status !== "authenticated" || !user) {
    return <Book label="Loading" left={<LoadingNote label="Opening your book…" />} />;
  }

  return (
    <Book
      label={label}
      left={left}
      right={right}
      chapters={chapters ? chaptersFor(user.timezone) : undefined}
    />
  );
}

/** Pages for signed-out visitors (sign in, sign up): bounce signed-in users home. */
export function PublicShell({ label, left, right }: { label: string; left: ReactNode; right?: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "authenticated") router.replace("/");
  }, [status, router]);
  return <Book label={label} left={left} right={right} startPage={1} />;
}
