"use client";

import { Check, Info, X } from "lucide-react";

import type { TimelineStep } from "@/lib/types";
import { cn } from "@/lib/utils";

export function VerificationTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="relative space-y-0">
      {steps.map((step, index) => {
        const Icon = step.ok === null ? Info : step.ok ? Check : X;
        const last = index === steps.length - 1;
        return (
          <li key={`${step.step}-${index}`} className="flex gap-3 pb-4 last:pb-0">
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "grid size-6 shrink-0 place-items-center rounded-full",
                  step.ok === null
                    ? "bg-neutral-soft text-muted"
                    : step.ok
                      ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                      : "bg-[var(--bad-soft)] text-[var(--bad)]",
                )}
              >
                <Icon className="size-3.5" strokeWidth={3} />
              </span>
              {last ? null : <span className="mt-1 w-px flex-1 bg-[var(--border)]" />}
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <p className="text-xs font-semibold">{step.step}</p>
                <span className="font-mono text-[10px] text-muted">
                  {new Date(step.at).toLocaleTimeString()}
                </span>
              </div>
              <p className="mt-0.5 text-xs leading-relaxed break-words text-muted">
                {step.detail}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
