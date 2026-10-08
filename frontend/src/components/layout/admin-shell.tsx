"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ChartNoAxesColumn,
  FileStack,
  LayoutDashboard,
  LogOut,
  ScrollText,
  ShieldAlert,
  Upload,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";

import { Brand } from "@/components/layout/brand";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/misc";
import { useAuth, useRequireRole } from "@/lib/auth";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/admin", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/admin/upload", label: "Issue documents", Icon: Upload },
  { href: "/admin/documents", label: "Document register", Icon: FileStack },
  { href: "/admin/analytics", label: "Analytics", Icon: ChartNoAxesColumn },
  { href: "/admin/audit-logs", label: "Audit trail", Icon: ScrollText },
  { href: "/admin/users", label: "Users", Icon: Users },
];

export function AdminShell({
  title,
  description,
  action,
  children,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { signOut } = useAuth();
  const { user, loading } = useRequireRole("admin");

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-[var(--border)] bg-surface lg:flex">
        <div className="border-b border-[var(--border)] px-4 py-4">
          <Link href="/">
            <Brand />
          </Link>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {nav.map(({ href, label, Icon }) => {
            const active = href === "/admin" ? pathname === href : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand-soft text-brand"
                    : "text-muted hover:bg-surface-muted hover:text-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-[var(--border)] p-3">
          <div className="mb-3 rounded-lg bg-surface-muted px-3 py-2.5">
            <p className="truncate text-xs font-semibold">{user?.name ?? "—"}</p>
            <p className="truncate text-[11px] text-muted">{user?.email ?? ""}</p>
          </div>
          <div className="flex items-center justify-between gap-2">
            <ThemeToggle />
            <Button
              size="sm"
              variant="ghost"
              icon={<LogOut className="size-3.5" />}
              onClick={() => {
                signOut();
                router.push("/");
              }}
            >
              Sign out
            </Button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="sticky top-0 z-30 border-b border-[var(--border)] bg-surface/85 px-4 py-4 backdrop-blur-md lg:px-8">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
              {description ? (
                <p className="mt-0.5 text-xs text-muted">{description}</p>
              ) : null}
            </div>
            {action}
          </div>
          <nav className="mt-3 flex gap-1 overflow-x-auto lg:hidden">
            {nav.map(({ href, label, Icon }) => {
              const active = href === "/admin" ? pathname === href : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium",
                    active ? "bg-brand-soft text-brand" : "text-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-3.5" />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>

        <main className="min-w-0 flex-1 p-4 lg:p-8">
          {loading ? (
            <div className="space-y-4">
              <Skeleton className="h-28 w-full" />
              <Skeleton className="h-64 w-full" />
            </div>
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
}

export function AdminError({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[var(--border)] bg-[var(--bad-soft)] px-4 py-3 text-sm text-[var(--bad)]">
      <ShieldAlert className="mt-0.5 size-4 shrink-0" />
      <p>{message}</p>
    </div>
  );
}
