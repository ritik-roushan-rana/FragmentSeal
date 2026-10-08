"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, LogOut, Menu, QrCode, ScanLine, X } from "lucide-react";
import { useState } from "react";

import { Brand } from "@/components/layout/brand";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Home" },
  { href: "/verify", label: "Verify document" },
  { href: "/verify/scan", label: "Scan QR" },
  { href: "/about", label: "How it works" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-surface/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4">
        <Link href="/" className="shrink-0">
          <Brand />
        </Link>

        <nav className="ml-4 hidden items-center gap-1 md:flex">
          {links.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand-soft text-brand"
                    : "text-muted hover:bg-surface-muted hover:text-foreground",
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <div className="hidden sm:block">
            <ThemeToggle />
          </div>

          {user ? (
            <div className="flex items-center gap-2">
              {user.role === "admin" ? (
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<LayoutDashboard className="size-3.5" />}
                  onClick={() => router.push("/admin")}
                  className="hidden sm:inline-flex"
                >
                  Console
                </Button>
              ) : null}
              <div className="hidden text-right lg:block">
                <p className="text-xs font-semibold">{user.name}</p>
                <p className="text-[10px] uppercase tracking-wide text-muted">{user.role}</p>
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label="Sign out"
                onClick={() => {
                  signOut();
                  router.push("/");
                }}
              >
                <LogOut className="size-4" />
              </Button>
            </div>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Button size="sm" variant="ghost" onClick={() => router.push("/login")}>
                Sign in
              </Button>
              <Button
                size="sm"
                icon={<ScanLine className="size-3.5" />}
                onClick={() => router.push("/verify")}
              >
                Verify a document
              </Button>
            </div>
          )}

          <Button
            size="icon"
            variant="ghost"
            className="md:hidden"
            aria-label="Toggle navigation"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </Button>
        </div>
      </div>

      {open ? (
        <div className="border-t border-[var(--border)] bg-surface px-4 py-3 md:hidden">
          <nav className="flex flex-col gap-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-surface-muted hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
            {user?.role === "admin" ? (
              <Link
                href="/admin"
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-brand"
              >
                Admin console
              </Link>
            ) : null}
            {!user ? (
              <Link
                href="/login"
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-brand"
              >
                Sign in
              </Link>
            ) : null}
          </nav>
          <div className="mt-3 flex items-center justify-between border-t border-[var(--border)] pt-3">
            <span className="flex items-center gap-1.5 text-xs text-muted">
              <QrCode className="size-3.5" /> QR-linked verification
            </span>
            <ThemeToggle />
          </div>
        </div>
      ) : null}
    </header>
  );
}
