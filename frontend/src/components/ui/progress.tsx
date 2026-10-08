import { cn } from "@/lib/utils";

export function Progress({
  value,
  max = 100,
  tone = "brand",
  className,
}: {
  value: number;
  max?: number;
  tone?: "brand" | "ok" | "warn" | "bad";
  className?: string;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const colors = {
    brand: "bg-brand",
    ok: "bg-[var(--ok)]",
    warn: "bg-[var(--warn)]",
    bad: "bg-[var(--bad)]",
  };
  return (
    <div
      className={cn("h-2 w-full overflow-hidden rounded-full bg-neutral-soft", className)}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={cn("h-full rounded-full transition-[width] duration-700", colors[tone])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
