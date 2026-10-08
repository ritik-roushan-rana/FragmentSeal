"use client";

import { useMemo, useState } from "react";

import { Badge, verdictTone } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Mono } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import type { FragmentAnalysis } from "@/lib/types";
import { shortHash } from "@/lib/utils";

export function FragmentTable({
  analysis,
  onSelect,
  selectedCell,
}: {
  analysis: FragmentAnalysis[];
  onSelect?: (fragment: FragmentAnalysis) => void;
  selectedCell?: number | null;
}) {
  const [filter, setFilter] = useState<"all" | "damaged" | "intact">("damaged");

  const rows = useMemo(() => {
    if (filter === "all") return analysis;
    if (filter === "intact") return analysis.filter((item) => item.status === "intact");
    return analysis.filter((item) => item.status !== "intact");
  }, [analysis, filter]);

  const damagedCount = analysis.filter((item) => item.status !== "intact").length;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
        <p className="text-xs text-muted">
          {damagedCount === 0
            ? `All ${analysis.length} fragments reproduced their issued hash.`
            : `${damagedCount} of ${analysis.length} fragments failed to reproduce their issued hash.`}
        </p>
        <Select
          value={filter}
          onChange={(event) => setFilter(event.target.value as typeof filter)}
          className="h-8 w-auto py-1 text-xs"
          aria-label="Filter fragments"
        >
          <option value="damaged">Affected only ({damagedCount})</option>
          <option value="all">All fragments ({analysis.length})</option>
          <option value="intact">Intact only ({analysis.length - damagedCount})</option>
        </Select>
      </div>

      <Table>
        <thead>
          <tr>
            <Th>Page</Th>
            <Th>Cell</Th>
            <Th>Status</Th>
            <Th>Signal</Th>
            <Th>Marker</Th>
            <Th>Issued hash</Th>
            <Th>Recomputed hash</Th>
            <Th>Observation</Th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <EmptyRow colSpan={8}>Nothing matches this filter.</EmptyRow>
          ) : (
            rows.map((item) => (
              <Tr
                key={`${item.page_index}-${item.cell_index}`}
                onClick={() => onSelect?.(item)}
                className={
                  selectedCell === item.cell_index
                    ? "cursor-pointer bg-brand-soft/60"
                    : "cursor-pointer"
                }
              >
                <Td className="tabular-nums">{item.page_index + 1}</Td>
                <Td className="font-mono text-xs">{item.cell_index}</Td>
                <Td>
                  <Badge tone={verdictTone[item.status] ?? "neutral"}>{item.status}</Badge>
                </Td>
                <Td className="whitespace-nowrap text-xs text-muted">
                  {item.status === "intact"
                    ? "—"
                    : [item.text_changed ? "text" : null, item.visual_changed ? "pixels" : null]
                        .filter(Boolean)
                        .join(" + ") || "digest"}
                </Td>
                <Td>
                  <Badge tone={verdictTone[item.marker_status] ?? "neutral"}>
                    {item.marker_status}
                  </Badge>
                </Td>
                <Td>
                  <Mono>{shortHash(item.expected_hash, 8, 6)}</Mono>
                </Td>
                <Td>
                  <Mono>{shortHash(item.actual_hash, 8, 6)}</Mono>
                </Td>
                <Td className="max-w-xs text-xs text-muted">{item.reason}</Td>
              </Tr>
            ))
          )}
        </tbody>
      </Table>
    </div>
  );
}
