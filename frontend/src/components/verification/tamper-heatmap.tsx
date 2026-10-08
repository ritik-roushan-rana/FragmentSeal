"use client";

/**
 * Renders the submitted page as an image and overlays one rectangle per
 * fragment. Intact fragments are drawn as a faint grid so the viewer can see
 * the fragmentation scheme; damaged fragments are tinted by severity, which is
 * the "tamper heatmap".
 */
import { Eye, EyeOff, Grid3x3, ZoomIn, ZoomOut } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import type { FragmentAnalysis, HeatmapRegion } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  modified: "var(--bad)",
  missing: "var(--warn)",
  added: "var(--accent)",
  intact: "var(--ok)",
};

export function TamperHeatmap({
  logId,
  pageCount,
  regions,
  analysis,
  onSelect,
  selectedCell,
}: {
  logId: string;
  pageCount: number;
  regions: HeatmapRegion[];
  analysis: FragmentAnalysis[];
  onSelect?: (fragment: FragmentAnalysis) => void;
  selectedCell?: number | null;
}) {
  const [page, setPage] = useState(0);
  const [showGrid, setShowGrid] = useState(true);
  const [showOverlay, setShowOverlay] = useState(true);
  const [zoom, setZoom] = useState(1);

  const pageAnalysis = useMemo(
    () => analysis.filter((item) => item.page_index === page && item.box),
    [analysis, page],
  );
  const pageRegions = useMemo(
    () => regions.filter((region) => region.page_index === page),
    [regions, page],
  );

  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  const src = `${apiBase}/api/v1/verify/logs/${logId}/pages/${page}?dpi=130`;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {pageCount > 1 ? (
          <div className="flex items-center gap-1 rounded-lg bg-surface-muted p-1">
            {Array.from({ length: pageCount }, (_, index) => (
              <button
                key={index}
                onClick={() => setPage(index)}
                className={cn(
                  "cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  page === index
                    ? "bg-surface text-foreground shadow-[var(--shadow-sm)]"
                    : "text-muted hover:text-foreground",
                )}
              >
                Page {index + 1}
                {regions.some((region) => region.page_index === index) ? (
                  <span className="ml-1 inline-block size-1.5 rounded-full bg-[var(--bad)]" />
                ) : null}
              </button>
            ))}
          </div>
        ) : null}

        <div className="ml-auto flex items-center gap-1.5">
          <Button
            size="sm"
            variant={showGrid ? "subtle" : "outline"}
            icon={<Grid3x3 className="size-3.5" />}
            onClick={() => setShowGrid((value) => !value)}
          >
            Grid
          </Button>
          <Button
            size="sm"
            variant={showOverlay ? "subtle" : "outline"}
            icon={showOverlay ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5" />}
            onClick={() => setShowOverlay((value) => !value)}
          >
            Overlay
          </Button>
          <Button
            size="icon"
            variant="outline"
            aria-label="Zoom out"
            onClick={() => setZoom((value) => Math.max(0.6, value - 0.2))}
          >
            <ZoomOut className="size-4" />
          </Button>
          <Button
            size="icon"
            variant="outline"
            aria-label="Zoom in"
            onClick={() => setZoom((value) => Math.min(2.4, value + 0.2))}
          >
            <ZoomIn className="size-4" />
          </Button>
        </div>
      </div>

      <div className="max-h-[70vh] overflow-auto rounded-xl border border-[var(--border)] bg-surface-muted p-4">
        <div
          className="relative mx-auto w-fit origin-top transition-transform"
          style={{ transform: `scale(${zoom})` }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={src}
            alt={`Submitted document, page ${page + 1}`}
            className="block max-w-full rounded-md shadow-[var(--shadow-md)]"
          />

          <div className="pointer-events-none absolute inset-0">
            {pageAnalysis.map((item) => {
              const box = item.box!;
              const damaged = item.status !== "intact";
              const region = pageRegions.find(
                (candidate) => candidate.cell_index === item.cell_index,
              );
              const severity = region?.severity ?? 0;
              const color = STATUS_COLOR[item.status] ?? "var(--muted)";
              if (!showGrid && !damaged) return null;
              if (!showOverlay && damaged) return null;
              const selected = selectedCell === item.cell_index;

              return (
                <button
                  key={`${item.page_index}-${item.cell_index}`}
                  onClick={() => onSelect?.(item)}
                  className={cn(
                    "pointer-events-auto absolute cursor-pointer border transition-all",
                    damaged ? "border-2" : "border-dashed",
                    selected && "ring-2 ring-offset-1",
                  )}
                  style={{
                    left: `${box.nx0 * 100}%`,
                    top: `${box.ny0 * 100}%`,
                    width: `${(box.nx1 - box.nx0) * 100}%`,
                    height: `${(box.ny1 - box.ny0) * 100}%`,
                    borderColor: damaged
                      ? color
                      : "color-mix(in srgb, var(--brand) 35%, transparent)",
                    background: damaged
                      ? `color-mix(in srgb, ${color} ${Math.round(18 + severity * 30)}%, transparent)`
                      : "transparent",
                  }}
                  title={
                    damaged
                      ? `Fragment ${item.cell_index}: ${item.status} — ${item.reason}`
                      : `Fragment ${item.cell_index}: intact`
                  }
                >
                  <span
                    className={cn(
                      "absolute top-0.5 left-0.5 rounded px-1 font-mono text-[9px] leading-tight",
                      damaged ? "text-white" : "text-muted/70",
                    )}
                    style={{ background: damaged ? color : "transparent" }}
                  >
                    {item.cell_index}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm border border-dashed border-brand/40" /> Fragment
          boundary
        </span>
        {["modified", "missing", "added"].map((status) => (
          <span key={status} className="flex items-center gap-1.5 capitalize">
            <span
              className="size-2.5 rounded-sm"
              style={{ background: STATUS_COLOR[status] }}
            />
            {status}
          </span>
        ))}
        <span className="ml-auto">Tint intensity tracks severity. Click a region for detail.</span>
      </div>
    </div>
  );
}
