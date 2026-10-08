import { ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";

export function Brand({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-brand to-[var(--accent)] text-white shadow-[var(--shadow-sm)]">
        <ShieldCheck className="size-5" />
      </span>
      {compact ? null : (
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-sm font-semibold tracking-tight">
            FragmentSeal
          </span>
          <span className="block truncate text-[10px] tracking-wide text-muted uppercase">
            Tamper-evident documents
          </span>
        </span>
      )}
    </span>
  );
}
