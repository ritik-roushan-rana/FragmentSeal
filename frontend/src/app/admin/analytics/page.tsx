"use client";

import { Activity, Flame, Grid3x3, TrendingUp } from "lucide-react";
import { useState } from "react";

import {
  ActivityAreaChart,
  FragmentBarChart,
  HotspotBarChart,
  VerdictPieChart,
} from "@/components/charts/charts";
import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Skeleton, StatRow } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import type { DashboardStats } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { percent } from "@/lib/utils";

interface Hotspots {
  hotspots: { page_index: number; cell_index: number; hits: number; avg_severity: number }[];
  sampled_logs: number;
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data: stats, error: statsError } = useApiResource<DashboardStats>(
    `/dashboard/stats?days=${days}`,
    { errorMessage: "Could not load analytics." },
  );
  const { data: hotspots, error: hotspotError } = useApiResource<Hotspots>(
    "/dashboard/tamper-hotspots",
    { errorMessage: "Could not load tamper hotspots." },
  );
  const error = statsError ?? hotspotError;

  const totals = stats?.totals;
  const checks = totals?.verification_requests ?? 0;
  const authentic = stats?.verifications_by_result.authentic ?? 0;
  const tampered =
    (stats?.verifications_by_result.tampered ?? 0) +
    (stats?.verifications_by_result.invalid ?? 0);

  return (
    <AdminShell
      title="Analytics"
      description="Issuance volume, verification outcomes and where documents get attacked."
      action={
        <Select
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
          className="h-9 w-auto text-xs"
          aria-label="Time window"
        >
          {[7, 14, 30, 60, 90].map((value) => (
            <option key={value} value={value}>
              Last {value} days
            </option>
          ))}
        </Select>
      }
    >
      <div className="space-y-5">
        {error ? <AdminError message={error} /> : null}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            {
              label: "Pass rate",
              value: `${percent(authentic, checks)}%`,
              detail: `${authentic} of ${checks} checks returned authentic`,
            },
            {
              label: "Tamper rate",
              value: `${percent(tampered, checks)}%`,
              detail: `${tampered} checks failed integrity or signature`,
            },
            {
              label: "Mean tamper score",
              value: totals?.avg_tamper_score ?? 0,
              detail: "across every recorded check",
            },
            {
              label: "Fragments under management",
              value: totals?.fragments ?? 0,
              detail: `${totals?.documents ?? 0} documents`,
            },
          ].map((tile) => (
            <Card key={tile.label}>
              <CardBody>
                <Badge tone="brand">{tile.label}</Badge>
                {stats ? (
                  <p className="mt-3 text-2xl font-semibold tabular-nums">{tile.value}</p>
                ) : (
                  <Skeleton className="mt-3 h-8 w-20" />
                )}
                <p className="mt-1 text-[11px] text-muted">{tile.detail}</p>
              </CardBody>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader
            title="Issuance and verification over time"
            description={`Daily counts for the last ${days} days.`}
            icon={<TrendingUp className="size-4" />}
          />
          <CardBody>
            {stats ? <ActivityAreaChart data={stats.series} /> : <Skeleton className="h-[260px]" />}
          </CardBody>
        </Card>

        <div className="grid gap-5 lg:grid-cols-3">
          <Card>
            <CardHeader title="Verdict mix" icon={<Activity className="size-4" />} />
            <CardBody>
              {stats ? (
                <VerdictPieChart data={stats.verifications_by_result} />
              ) : (
                <Skeleton className="h-[220px]" />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Register composition" icon={<Grid3x3 className="size-4" />} />
            <CardBody>
              {stats ? (
                <FragmentBarChart
                  data={[
                    {
                      label: "Active",
                      value: stats.totals.active,
                      tone: "var(--ok)",
                    },
                    {
                      label: "Revoked",
                      value: stats.totals.revoked,
                      tone: "var(--warn)",
                    },
                    {
                      label: "Flagged",
                      value: stats.totals.documents_flagged,
                      tone: "var(--bad)",
                    },
                    {
                      label: "Failed",
                      value: stats.totals.failed,
                      tone: "var(--muted)",
                    },
                  ]}
                />
              ) : (
                <Skeleton className="h-[200px]" />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Tamper hotspots"
              description="Which grid cells attackers target."
              icon={<Flame className="size-4" />}
            />
            <CardBody>
              {hotspots ? (
                <HotspotBarChart data={hotspots.hotspots} />
              ) : (
                <Skeleton className="h-[200px]" />
              )}
            </CardBody>
          </Card>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Hotspot detail"
              description={
                hotspots
                  ? `Sampled from ${hotspots.sampled_logs} failing verification(s).`
                  : undefined
              }
            />
            <Table>
              <thead>
                <tr>
                  <Th>Page</Th>
                  <Th>Cell</Th>
                  <Th>Times altered</Th>
                  <Th>Mean severity</Th>
                </tr>
              </thead>
              <tbody>
                {!hotspots?.hotspots.length ? (
                  <EmptyRow colSpan={4}>
                    No tampering recorded yet. Use the sandbox on a document to generate a case.
                  </EmptyRow>
                ) : (
                  hotspots.hotspots.slice(0, 12).map((item) => (
                    <Tr key={`${item.page_index}-${item.cell_index}`}>
                      <Td className="tabular-nums">{item.page_index + 1}</Td>
                      <Td className="font-mono text-xs">{item.cell_index}</Td>
                      <Td className="tabular-nums">{item.hits}</Td>
                      <Td className="tabular-nums">{item.avg_severity}</Td>
                    </Tr>
                  ))
                )}
              </tbody>
            </Table>
          </Card>

          <Card>
            <CardHeader title="Totals" />
            <CardBody>
              {stats ? (
                <div>
                  <StatRow label="Documents issued" value={stats.totals.documents} />
                  <StatRow label="Active" value={stats.totals.active} />
                  <StatRow label="Revoked" value={stats.totals.revoked} />
                  <StatRow label="Failed to protect" value={stats.totals.failed} />
                  <StatRow label="Fragment hashes" value={stats.totals.fragments} />
                  <StatRow label="Verification requests" value={stats.totals.verification_requests} />
                  <StatRow label="Documents verified clean" value={stats.totals.documents_verified_clean} />
                  <StatRow label="Documents flagged" value={stats.totals.documents_flagged} />
                  <StatRow label="Registered users" value={stats.totals.users} />
                </div>
              ) : (
                <Skeleton className="h-64" />
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </AdminShell>
  );
}
