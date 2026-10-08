"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  FileCheck2,
  FileStack,
  FileWarning,
  Fingerprint,
  Plus,
  RefreshCw,
  ScanLine,
  ShieldOff,
  Sparkles,
} from "lucide-react";
import { useState } from "react";

import { ActivityAreaChart, VerdictPieChart } from "@/components/charts/charts";
import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Mono, Skeleton } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError, apiPost } from "@/lib/api";
import type { DashboardStats } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { formatDateTime, relativeTime } from "@/lib/utils";

export default function AdminDashboardPage() {
  const {
    data: stats,
    error,
    loading,
    reload,
  } = useApiResource<DashboardStats>("/dashboard/stats?days=14", {
    pollMs: 20000,
    errorMessage: "Could not load dashboard statistics.",
  });
  const [actionError, setActionError] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  async function issueSamples() {
    setSeeding(true);
    setActionError(null);
    try {
      await apiPost("/documents/samples");
      reload();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not issue the sample documents.",
      );
    } finally {
      setSeeding(false);
    }
  }

  const totals = stats?.totals;
  const tiles = [
    {
      label: "Documents issued",
      value: totals?.documents ?? 0,
      detail: `${totals?.active ?? 0} active · ${totals?.processing ?? 0} processing`,
      Icon: FileStack,
      tone: "brand" as const,
    },
    {
      label: "Verified clean",
      value: totals?.documents_verified_clean ?? 0,
      detail: "documents that passed at least one check",
      Icon: FileCheck2,
      tone: "ok" as const,
    },
    {
      label: "Tampered / flagged",
      value: totals?.documents_flagged ?? 0,
      detail: `${totals?.tampered_verifications ?? 0} failing checks recorded`,
      Icon: FileWarning,
      tone: "bad" as const,
    },
    {
      label: "Revoked",
      value: totals?.revoked ?? 0,
      detail: "withdrawn by the issuer",
      Icon: ShieldOff,
      tone: "warn" as const,
    },
    {
      label: "Verification requests",
      value: totals?.verification_requests ?? 0,
      detail: `mean tamper score ${totals?.avg_tamper_score ?? 0}`,
      Icon: ScanLine,
      tone: "accent" as const,
    },
    {
      label: "Fragment hashes",
      value: totals?.fragments ?? 0,
      detail: "SHA-256 leaves under management",
      Icon: Fingerprint,
      tone: "neutral" as const,
    },
  ];

  return (
    <AdminShell
      title="Dashboard"
      description="Issuance, verification and tamper activity across the register."
      action={
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            loading={seeding}
            icon={<Sparkles className="size-3.5" />}
            onClick={issueSamples}
          >
            Issue sample documents
          </Button>
          <Button variant="ghost" size="sm" icon={<RefreshCw className="size-3.5" />} onClick={reload}>
            Refresh
          </Button>
          <Link href="/admin/upload">
            <Button size="sm" icon={<Plus className="size-3.5" />}>
              Protect a document
            </Button>
          </Link>
        </div>
      }
    >
      <div className="space-y-5">
        {error ?? actionError ? (
          <AdminError message={(error ?? actionError) as string} />
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {tiles.map(({ label, value, detail, Icon, tone }) => (
            <Card key={label}>
              <CardBody>
                <div className="flex items-start justify-between gap-2">
                  <Badge tone={tone}>{label}</Badge>
                  <Icon className="size-4 shrink-0 text-muted" />
                </div>
                {loading && !stats ? (
                  <Skeleton className="mt-3 h-8 w-16" />
                ) : (
                  <p className="mt-3 text-2xl font-semibold tabular-nums">{value}</p>
                )}
                <p className="mt-1 text-[11px] leading-relaxed text-muted">{detail}</p>
              </CardBody>
            </Card>
          ))}
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Issuance and verification"
              description={`Daily counts over the last ${stats?.window_days ?? 14} days.`}
              icon={<Activity className="size-4" />}
            />
            <CardBody>
              {stats ? (
                <ActivityAreaChart data={stats.series} />
              ) : (
                <Skeleton className="h-[260px] w-full" />
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Verdict mix" description="All verifications to date." />
            <CardBody>
              {stats ? (
                <VerdictPieChart data={stats.verifications_by_result} />
              ) : (
                <Skeleton className="h-[220px] w-full" />
              )}
            </CardBody>
          </Card>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Recent verifications"
              action={
                <Link href="/verify/history">
                  <Button size="sm" variant="ghost">
                    All <ArrowRight className="size-3.5" />
                  </Button>
                </Link>
              }
            />
            <Table>
              <thead>
                <tr>
                  <Th>File</Th>
                  <Th>Verdict</Th>
                  <Th>Score</Th>
                  <Th>When</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {!stats?.recent_verifications.length ? (
                  <EmptyRow colSpan={5}>No verifications yet.</EmptyRow>
                ) : (
                  stats.recent_verifications.map((log) => (
                    <Tr key={log.id}>
                      <Td className="max-w-[12rem] truncate">{log.file_name || "—"}</Td>
                      <Td>
                        <Badge tone={verdictTone[log.result] ?? "neutral"}>{log.result}</Badge>
                      </Td>
                      <Td className="tabular-nums">{log.tamper_score}</Td>
                      <Td className="whitespace-nowrap text-xs text-muted">
                        {relativeTime(log.timestamp)}
                      </Td>
                      <Td>
                        <Link href={`/verify/result/${log.id}`}>
                          <Button size="sm" variant="ghost">
                            View
                          </Button>
                        </Link>
                      </Td>
                    </Tr>
                  ))
                )}
              </tbody>
            </Table>
          </Card>

          <Card>
            <CardHeader
              title="Recent activity"
              description="Audit trail — issuance, revocation, verification, administration."
              action={
                <Link href="/admin/audit-logs">
                  <Button size="sm" variant="ghost">
                    All <ArrowRight className="size-3.5" />
                  </Button>
                </Link>
              }
            />
            <CardBody>
              {!stats?.recent_activity.length ? (
                <p className="py-8 text-center text-sm text-muted">Nothing recorded yet.</p>
              ) : (
                <ul className="space-y-3">
                  {stats.recent_activity.map((entry) => (
                    <li key={entry.id} className="flex gap-3">
                      <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-brand" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-baseline gap-x-2">
                          <Mono>{entry.action}</Mono>
                          <span className="text-[10px] text-muted">
                            {relativeTime(entry.timestamp)}
                          </span>
                        </div>
                        <p className="mt-0.5 text-xs break-words text-muted">
                          {entry.detail || "—"}
                          {entry.user_email ? ` · ${entry.user_email}` : ""}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
        </div>

        {stats?.top_documents.length ? (
          <Card>
            <CardHeader
              title="Most-checked documents"
              description="High check counts can indicate a document in wide circulation — or one being probed."
            />
            <Table>
              <thead>
                <tr>
                  <Th>Document</Th>
                  <Th>Status</Th>
                  <Th>Checks</Th>
                  <Th>Mean tamper score</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {stats.top_documents.map((item) => (
                  <Tr key={item.document_id}>
                    <Td className="max-w-[18rem] truncate">{item.name}</Td>
                    <Td>
                      <Badge tone={verdictTone[item.status] ?? "neutral"}>{item.status}</Badge>
                    </Td>
                    <Td className="tabular-nums">{item.checks}</Td>
                    <Td className="tabular-nums">{item.avg_tamper_score}</Td>
                    <Td>
                      <Link href={`/admin/documents/${item.document_id}`}>
                        <Button size="sm" variant="ghost">
                          Open
                        </Button>
                      </Link>
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          </Card>
        ) : null}

        {stats ? (
          <p className="text-[11px] text-muted">
            Last refreshed {formatDateTime(new Date().toISOString())} · auto-refreshes every 20 s
          </p>
        ) : null}
      </div>
    </AdminShell>
  );
}
