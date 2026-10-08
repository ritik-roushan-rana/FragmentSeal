import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type Tone = "neutral" | "brand" | "ok" | "warn" | "bad" | "accent";

const tones: Record<Tone, string> = {
  neutral: "bg-neutral-soft text-muted",
  brand: "bg-brand-soft text-brand",
  ok: "bg-[var(--ok-soft)] text-[var(--ok)]",
  warn: "bg-[var(--warn-soft)] text-[var(--warn)]",
  bad: "bg-[var(--bad-soft)] text-[var(--bad)]",
  accent: "bg-brand-soft text-[var(--accent)]",
};

export function Badge({
  tone = "neutral",
  className,
  children,
  icon,
}: {
  tone?: Tone;
  className?: string;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tones[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  );
}

export const verdictTone: Record<string, Tone> = {
  authentic: "ok",
  tampered: "bad",
  invalid: "bad",
  revoked: "warn",
  unknown: "neutral",
  active: "ok",
  processing: "brand",
  failed: "bad",
  intact: "ok",
  modified: "bad",
  missing: "warn",
  added: "accent",
  valid: "ok",
  mismatch: "bad",
  absent: "warn",
};
