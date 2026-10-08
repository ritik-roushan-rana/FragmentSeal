"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { UserPlus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/misc";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { signUp } = useAuth();
  const [form, setForm] = useState({
    name: "",
    email: "",
    organization: "",
    password: "",
    confirm: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update(key: keyof typeof form) {
    return (event: React.ChangeEvent<HTMLInputElement>) =>
      setForm((previous) => ({ ...previous, [key]: event.target.value }));
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (form.password !== form.confirm) {
      setError("The two passwords do not match.");
      return;
    }
    if (form.password.length < 8) {
      setError("Use at least 8 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await signUp({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        organization: form.organization.trim() || undefined,
      });
      router.replace("/verify");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not register. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Create a verifier account</h1>
      <p className="mt-2 text-sm text-muted">
        An account keeps a history of your checks and lets you e-mail reports. Issuing
        documents requires an admin account, which an existing admin provisions.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-4">
        {error ? <Alert tone="bad">{error}</Alert> : null}

        <Field label="Full name" htmlFor="name">
          <Input id="name" required value={form.name} onChange={update("name")} />
        </Field>

        <Field label="Email" htmlFor="email">
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update("email")}
          />
        </Field>

        <Field label="Organisation" hint="Optional — shown on verification records." htmlFor="org">
          <Input id="org" value={form.organization} onChange={update("organization")} />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              value={form.password}
              onChange={update("password")}
            />
          </Field>
          <Field label="Confirm password" htmlFor="confirm">
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              required
              value={form.confirm}
              onChange={update("confirm")}
            />
          </Field>
        </div>

        <Button
          type="submit"
          className="w-full"
          size="lg"
          loading={busy}
          icon={<UserPlus className="size-4" />}
        >
          Create account
        </Button>
      </form>

      <p className="mt-6 text-center text-xs text-muted">
        Already registered?{" "}
        <Link href="/login" className="font-medium text-brand hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
