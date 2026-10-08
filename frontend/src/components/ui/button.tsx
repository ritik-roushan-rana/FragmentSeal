"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline" | "subtle";
type Size = "sm" | "md" | "lg" | "icon";

const variants: Record<Variant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand-strong shadow-sm disabled:bg-brand/50 focus-visible:outline-brand",
  secondary:
    "bg-surface-muted text-foreground hover:bg-neutral-soft border border-[var(--border)]",
  outline:
    "border border-[var(--border-strong)] text-foreground hover:bg-surface-muted bg-transparent",
  ghost: "text-muted hover:text-foreground hover:bg-surface-muted",
  danger: "bg-[var(--bad)] text-white hover:brightness-110 shadow-sm",
  subtle: "bg-brand-soft text-brand hover:brightness-105 border border-[var(--border)]",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2.5",
  icon: "h-9 w-9 justify-center",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex cursor-pointer items-center rounded-lg font-medium transition-all",
        "focus-visible:outline-2 focus-visible:outline-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-60",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="size-4 shrink-0 animate-spin" /> : icon}
      {children}
    </button>
  );
}
