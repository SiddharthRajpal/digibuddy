"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

import { Spread } from "@/components/book/Book";
import { LoadingNote } from "@/components/ui/Controls";
import { useAuth } from "@/lib/auth";

export interface AppShellProps {
  label: string;
  left: ReactNode;
  right?: ReactNode;
}

/**
 * Signed-in pages: sends visitors to sign in (or to onboarding) first, then shows the
 * spread. The book itself lives in the root layout and never remounts.
 */
export function AppShell({ label, left, right }: AppShellProps) {
  const { status, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${encodeURIComponent(pathname ?? "/")}`);
    else if (status === "authenticated" && user && !user.onboarding_completed && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [status, user, router, pathname]);

  const ready = status === "authenticated" && Boolean(user);
  return (
    <Spread
      label={label}
      left={ready ? left : <LoadingNote label="Opening your book…" />}
      right={ready ? right : undefined}
    />
  );
}

/**
 * Pages for signed-out visitors (sign in, sign up): bounce visitors who arrive already
 * signed in. Someone who signs in *here* is moved on by the form itself (to onboarding or
 * where they were going), so this must not race it with a second navigation.
 */
export function PublicShell({ label, left, right }: { label: string; left: ReactNode; right?: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const wasSignedOut = useRef(false);
  useEffect(() => {
    if (status === "anonymous") wasSignedOut.current = true;
    if (status === "authenticated" && !wasSignedOut.current) router.replace("/");
  }, [status, router]);
  return <Spread label={label} left={left} right={right} startPage={1} />;
}
