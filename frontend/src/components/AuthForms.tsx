"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Controls";
import { TextField } from "@/components/ui/TextField";
import { useAuth } from "@/lib/auth";
import { browserTimeZone } from "@/lib/dates";
import { loginSchema, signupSchema, type LoginValues, type SignupValues } from "@/lib/schemas";

function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

export function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<LoginValues>({ resolver: zodResolver(loginSchema), defaultValues: { email: "", password: "" } });
  const e = form.formState.errors;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await login(v);
      router.replace(safeNext(params?.get("next") ?? null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't sign you in.");
    }
  });
  return (
    <form onSubmit={onSubmit} noValidate className="stack" aria-label="Sign in">
      <TextField label="Email" type="email" autoComplete="email" error={e.email?.message} {...form.register("email")} />
      <TextField label="Password" type="password" autoComplete="current-password" error={e.password?.message} {...form.register("password")} />
      {error ? <ErrorNote message={error} /> : null}
      <Button type="submit" block loading={form.formState.isSubmitting}>
        Open my book
      </Button>
      <p className="t-body-sm">
        New here? <Link href="/signup">Start a new book</Link>
      </p>
    </form>
  );
}

export function SignupForm() {
  const { signup } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { display_name: "", email: "", password: "" },
  });
  const e = form.formState.errors;
  const onSubmit = form.handleSubmit(async (v) => {
    setError(null);
    try {
      await signup({ ...v, timezone: browserTimeZone() });
      router.replace("/onboarding");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create your book.");
    }
  });
  return (
    <form onSubmit={onSubmit} noValidate className="stack" aria-label="Sign up">
      <TextField label="What should I call you?" autoComplete="nickname" error={e.display_name?.message} {...form.register("display_name")} />
      <TextField label="Email" type="email" autoComplete="email" error={e.email?.message} {...form.register("email")} />
      <TextField
        label="Password"
        type="password"
        autoComplete="new-password"
        hint="At least 8 characters."
        error={e.password?.message}
        {...form.register("password")}
      />
      {error ? <ErrorNote message={error} /> : null}
      <Button type="submit" block loading={form.formState.isSubmitting}>
        Start my book
      </Button>
      <p className="t-body-sm">
        Already have a book? <Link href="/login">Sign in</Link>
      </p>
    </form>
  );
}
