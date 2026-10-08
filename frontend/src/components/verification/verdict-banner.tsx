"use client";

import {
  BadgeCheck,
  CircleSlash,
  FileQuestion,
  ShieldAlert,
  ShieldX,
} from "lucide-react";

import { Progress } from "@/components/ui/progress";
import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

const config: Record<
  Verdict,
  { Icon: typeof BadgeCheck; title: string; blurb: string; tone: string; bar: "ok" | "warn" | "bad" }
> = {
  authentic: {
    Icon: BadgeCheck,
    title: "Authentic",
    blurb:
      "Every fragment reproduced its issued hash, the Merkle root matches the signed root, and the watermark decoded cleanly.",
    tone: "text-[var(--ok)] bg-[var(--ok-soft)]",
    bar: "ok",
  },
  tampered: {
    Icon: ShieldAlert,
    title: "Tampered",
    blurb:
      "The signature is genuine but the content no longer hashes to the signed Merkle root. The affected regions are highlighted below.",
    tone: "text-[var(--bad)] bg-[var(--bad-soft)]",
    bar: "bad",
  },
  invalid: {
    Icon: ShieldX,
    title: "Invalid signature",
    blurb:
      "The signature over the Merkle root does not validate against any registered public key. Treat this document as forged.",
    tone: "text-[var(--bad)] bg-[var(--bad-soft)]",
    bar: "bad",
  },
  revoked: {
    Icon: CircleSlash,
    title: "Revoked",
    blurb:
      "This document was issued by the authority and is cryptographically intact, but the issuer has since withdrawn it.",
    tone: "text-[var(--warn)] bg-[var(--warn-soft)]",
    bar: "warn",
  },
  unknown: {
    Icon: FileQuestion,
    title: "Not recognised",
    blurb:
      "This file carries no verification data from this authority, so there is nothing to check it against.",
    tone: "text-muted bg-neutral-soft",
    bar: "warn",
  },
};

export function VerdictBanner({
  verdict,
  score,
  fileName,
  verifiedAt,
  durationMs,
  revokedReason,
}: {
  verdict: Verdict;
  score: number;
  fileName: string;
  verifiedAt: string;
  durationMs: number;
  revokedReason?: string | null;
}) {
  const { Icon, title, blurb, tone, bar } = config[verdict] ?? config.unknown;

  return (
    <div
      className={cn(
        "animate-fade-up overflow-hidden rounded-xl border border-[var(--border)] bg-surface shadow-[var(--shadow-sm)]",
      )}
    >
      <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-start">
        <span
          className={cn(
            "grid size-14 shrink-0 place-items-center rounded-xl",
            tone,
            verdict === "tampered" || verdict === "invalid" ? "animate-pulse-ring" : "",
          )}
        >
          <Icon className="size-7" />
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
            <span className="rounded-md bg-surface-muted px-2 py-0.5 font-mono text-[11px] text-muted">
              {fileName}
            </span>
          </div>
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">{blurb}</p>
          {revokedReason ? (
            <p className="mt-2 rounded-lg bg-[var(--warn-soft)] px-3 py-2 text-xs text-[var(--warn)]">
              Issuer’s reason: {revokedReason}
            </p>
          ) : null}
          <p className="mt-2 text-[11px] text-muted">
            Checked {new Date(verifiedAt).toLocaleString()} · {durationMs} ms
          </p>
        </div>

        <div className="w-full shrink-0 sm:w-44">
          <div className="flex items-end justify-between">
            <span className="text-[10px] uppercase tracking-wide text-muted">Tamper score</span>
            <span className="text-2xl font-semibold tabular-nums">{score}</span>
          </div>
          <Progress value={score} tone={bar} className="mt-2" />
          <p className="mt-1.5 text-[10px] leading-relaxed text-muted">
            0 = byte-for-byte as issued · 100 = nothing verifiable survived
          </p>
        </div>
      </div>
    </div>
  );
}
