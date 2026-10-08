"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { LogIn } from "lucide-react";
import { Suspense, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/misc";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const demoAccounts = [
  { label: "Admin (issuer)", email: "admin@docauth.dev", password: "Admin@12345" },
  { label: "Verifier", email: "verifier@docauth.dev", password: "Verify@12345" },
];

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { signIn, user } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const next = params.get("next");

  useEffect(() => {
    if (user) router.replace(next || (user.role === "admin" ? "/admin" : "/verify"));
  }, [user, next, router]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const signedIn = await signIn(email.trim(), password);
      router.replace(next || (signedIn.role === "admin" ? "/admin" : "/verify"));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not sign in. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="mt-2 text-sm text-muted">
        Issuers manage and protect documents. Verification itself needs no account.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        {error ? <Alert tone="bad">{error}</Alert> : null}

        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@organisation.example"
          />
        </Field>

        <Field label="Password" htmlFor="password">
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
          />
        </Field>

        <Button
          type="submit"
          className="w-full"
          size="lg"
          loading={busy}
          icon={<LogIn className="size-4" />}
        >
          Sign in
        </Button>
      </form>

      <div className="mt-6 rounded-lg border border-[var(--border)] bg-surface-muted p-4">
        <p className="text-xs font-semibold">Demo accounts</p>
        <p className="mt-1 text-[11px] text-muted">
          Seeded by <code className="font-mono">python -m app.seed</code>. Click to fill the form.
        </p>
        <div className="mt-3 space-y-2">
          {demoAccounts.map((account) => (
            <button
              key={account.email}
              type="button"
              onClick={() => {
                setEmail(account.email);
                setPassword(account.password);
              }}
              className="flex w-full cursor-pointer items-center justify-between gap-3 rounded-lg border border-[var(--border)] bg-surface px-3 py-2 text-left transition-colors hover:border-brand"
            >
              <span className="text-xs font-medium">{account.label}</span>
              <span className="font-mono text-[10px] text-muted">{account.email}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="mt-6 text-center text-xs text-muted">
        Need a verifier account?{" "}
        <Link href="/register" className="font-medium text-brand hover:underline">
          Register
        </Link>
      </p>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="h-80 animate-pulse rounded-xl bg-surface-muted" />}>
      <LoginForm />
    </Suspense>
  );
}
