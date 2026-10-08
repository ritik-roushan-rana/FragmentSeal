"use client";

import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { useEffect, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-neutral-soft", className)} />;
}

export function Alert({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: "info" | "ok" | "warn" | "bad";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const config = {
    info: { cls: "bg-brand-soft text-brand", Icon: Info },
    ok: { cls: "bg-[var(--ok-soft)] text-[var(--ok)]", Icon: CheckCircle2 },
    warn: { cls: "bg-[var(--warn-soft)] text-[var(--warn)]", Icon: AlertTriangle },
    bad: { cls: "bg-[var(--bad-soft)] text-[var(--bad)]", Icon: XCircle },
  }[tone];

  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-lg border border-[var(--border)] px-4 py-3 text-sm",
        config.cls,
        className,
      )}
      role="status"
    >
      <config.Icon className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 flex-1">
        {title ? <p className="font-semibold">{title}</p> : null}
        {children ? <div className="text-current/90 [&:not(:first-child)]:mt-1">{children}</div> : null}
      </div>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <button
        aria-label="Close dialog"
        className="absolute inset-0 cursor-default bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="animate-fade-up relative w-full max-w-lg rounded-xl border border-[var(--border)] bg-surface shadow-[var(--shadow-lg)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] px-5 py-4">
          <div>
            <h2 className="text-base font-semibold">{title}</h2>
            {description ? <p className="mt-1 text-xs text-muted">{description}</p> : null}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="cursor-pointer rounded-md p-1 text-muted transition-colors hover:bg-surface-muted hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        </div>
        {children ? <div className="px-5 py-4">{children}</div> : null}
        {footer ? (
          <div className="flex justify-end gap-2 border-t border-[var(--border)] px-5 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <code
      className={cn(
        "rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[11px] break-all text-foreground/90",
        className,
      )}
    >
      {children}
    </code>
  );
}

export function StatRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-[var(--border)] py-2 last:border-0">
      <span className="shrink-0 text-xs text-muted">{label}</span>
      <span
        className={cn(
          "min-w-0 text-right text-xs font-medium break-all",
          mono && "font-mono text-[11px]",
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string; count?: number }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex gap-1 overflow-x-auto rounded-lg bg-surface-muted p-1"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={value === tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "cursor-pointer rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors",
            value === tab.id
              ? "bg-surface text-foreground shadow-[var(--shadow-sm)]"
              : "text-muted hover:text-foreground",
          )}
        >
          {tab.label}
          {typeof tab.count === "number" ? (
            <span className="ml-1.5 text-[10px] opacity-70">{tab.count}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}
