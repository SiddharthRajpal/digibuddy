"use client";

import { Suspense } from "react";

import { PublicShell } from "@/components/AppShell";
import { LoginForm } from "@/components/AuthForms";
import { Endpaper } from "@/components/Endpaper";
import { LoadingNote } from "@/components/ui/Controls";

export default function LoginPage() {
  return (
    <PublicShell
      label="Sign in"
      left={<Endpaper />}
      right={
        <div className="stack-lg">
          <header className="stack">
            <p className="eyebrow">Welcome back</p>
            <h2 className="t-title-lg">Open your book</h2>
          </header>
          <Suspense fallback={<LoadingNote />}>
            <LoginForm />
          </Suspense>
        </div>
      }
    />
  );
}
