"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

type Mode = "light" | "dark" | "system";
const KEY = "docauth.theme";

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>("system");

  // Read the stored preference after hydration (in a microtask) so the
  // server-rendered markup and the first client render agree.
  useEffect(() => {
    let active = true;
    void Promise.resolve()
      .then(() => {
        try {
          return window.localStorage.getItem(KEY) as Mode | null;
        } catch {
          return null; // private browsing: keep following the system setting
        }
      })
      .then((stored) => {
        if (active && stored) setMode(stored);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    if (mode === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", mode);
    try {
      window.localStorage.setItem(KEY, mode);
    } catch {
      // ignore
    }
  }, [mode]);

  const options: { id: Mode; Icon: typeof Sun; label: string }[] = [
    { id: "light", Icon: Sun, label: "Light" },
    { id: "dark", Icon: Moon, label: "Dark" },
    { id: "system", Icon: Monitor, label: "System" },
  ];

  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-[var(--border)] bg-surface-muted p-0.5">
      {options.map(({ id, Icon, label }) => (
        <button
          key={id}
          onClick={() => setMode(id)}
          aria-label={`${label} theme`}
          aria-pressed={mode === id}
          className={cn(
            "cursor-pointer rounded-md p-1.5 transition-colors",
            mode === id
              ? "bg-surface text-foreground shadow-[var(--shadow-sm)]"
              : "text-muted hover:text-foreground",
          )}
        >
          <Icon className="size-3.5" />
        </button>
      ))}
    </div>
  );
}
