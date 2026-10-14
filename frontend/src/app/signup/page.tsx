"use client";

import { PublicShell } from "@/components/AppShell";
import { SignupForm } from "@/components/AuthForms";
import { Endpaper } from "@/components/Endpaper";

export default function SignupPage() {
  return (
    <PublicShell
      label="Sign up"
      left={<Endpaper />}
      right={
        <div className="stack-lg">
          <header className="stack">
            <p className="eyebrow">First page</p>
            <h2 className="t-title-lg">Start your book</h2>
          </header>
          <SignupForm />
        </div>
      }
    />
  );
}
