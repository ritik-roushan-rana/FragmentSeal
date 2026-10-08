"use client";

import { Check, Minus, X } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function CheckTile({
  label,
  ok,
  detail,
  children,
}: {
  label: string;
  ok: boolean | null;
  detail: ReactNode;
  children?: ReactNode;
}) {
  const Icon = ok === null ? Minus : ok ? Check : X;
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface p-4 shadow-[var(--shadow-sm)]">
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "grid size-7 shrink-0 place-items-center rounded-lg",
            ok === null
              ? "bg-neutral-soft text-muted"
              : ok
                ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                : "bg-[var(--bad-soft)] text-[var(--bad)]",
          )}
        >
          <Icon className="size-4" strokeWidth={3} />
        </span>
        <h4 className="text-sm font-semibold">{label}</h4>
      </div>
      <p className="mt-2.5 text-xs leading-relaxed text-muted">{detail}</p>
      {children}
    </div>
  );
}
