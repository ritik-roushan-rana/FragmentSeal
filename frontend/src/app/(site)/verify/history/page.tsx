"use client";

import Link from "next/link";
import { ArrowRight, History, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Alert, Mono, Skeleton } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import type { Paginated, VerificationLog, Verdict } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { formatDateTime, relativeTime } from "@/lib/utils";

const verdicts: (Verdict | "")[] = ["", "authentic", "tampered", "revoked", "invalid", "unknown"];

export default function VerificationHistoryPage() {
  const [filter, setFilter] = useState<Verdict | "">("");
  const [page, setPage] = useState(1);

  const path = useMemo(() => {
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    if (filter) query.set("result", filter);
    return `/verify/logs?${query}`;
  }, [filter, page]);

  const { data, error, loading, reload } = useApiResource<Paginated<VerificationLog>>(path, {
    auth: false,
    errorMessage: "Could not load the history.",
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Verification history</h1>
          <p className="mt-2 max-w-xl text-sm text-muted">
            Every check performed on this platform, with its verdict and tamper score. Records
            are append-only.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select
            aria-label="Filter by verdict"
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value as Verdict | "");
              setPage(1);
            }}
            className="h-10 w-auto"
          >
            {verdicts.map((value) => (
              <option key={value} value={value}>
                {value === "" ? "All verdicts" : value}
              </option>
            ))}
          </Select>
          <Button variant="outline" icon={<RefreshCw className="size-4" />} onClick={reload}>
            Refresh
          </Button>
        </div>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Checks"
          description={data ? `${data.total} record(s)` : undefined}
          icon={<History className="size-4" />}
        />
        {error ? (
          <CardBody>
            <Alert tone="bad">{error}</Alert>
          </CardBody>
        ) : loading && !data ? (
          <CardBody className="space-y-2">
            {Array.from({ length: 6 }, (_, index) => (
              <Skeleton key={index} className="h-10 w-full" />
            ))}
          </CardBody>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>File</Th>
                  <Th>Verdict</Th>
                  <Th>Score</Th>
                  <Th>Fragments</Th>
                  <Th>Checks</Th>
                  <Th>Verifier</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {!data?.items.length ? (
                  <EmptyRow colSpan={8}>No verifications recorded yet.</EmptyRow>
                ) : (
                  data.items.map((log) => (
                    <Tr key={log.id}>
                      <Td className="whitespace-nowrap">
                        <span title={formatDateTime(log.timestamp)}>
                          {relativeTime(log.timestamp)}
                        </span>
                      </Td>
                      <Td className="max-w-[16rem] truncate">{log.file_name || "—"}</Td>
                      <Td>
                        <Badge tone={verdictTone[log.result] ?? "neutral"}>{log.result}</Badge>
                      </Td>
                      <Td className="tabular-nums">{log.tamper_score}</Td>
                      <Td className="whitespace-nowrap text-xs text-muted">
                        {log.fragments_total - log.fragments_modified}/{log.fragments_total} intact
                      </Td>
                      <Td>
                        <span className="flex gap-1">
                          {[
                            ["QR", log.qr_found],
                            ["SIG", log.signature_valid],
                            ["MRK", log.merkle_match],
                            ["WM", log.watermark_valid],
                          ].map(([label, ok]) => (
                            <span
                              key={label as string}
                              className={`rounded px-1 py-0.5 font-mono text-[9px] ${
                                ok
                                  ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                                  : "bg-[var(--bad-soft)] text-[var(--bad)]"
                              }`}
                              title={`${label}: ${ok ? "pass" : "fail"}`}
                            >
                              {label as string}
                            </span>
                          ))}
                        </span>
                      </Td>
                      <Td className="text-xs text-muted">
                        <Mono>{log.verifier}</Mono>
                      </Td>
                      <Td>
                        <Link href={`/verify/result/${log.id}`}>
                          <Button size="sm" variant="ghost">
                            Report <ArrowRight className="size-3.5" />
                          </Button>
                        </Link>
                      </Td>
                    </Tr>
                  ))
                )}
              </tbody>
            </Table>

            {data && data.pages > 1 ? (
              <div className="flex items-center justify-between px-5 py-3">
                <p className="text-xs text-muted">
                  Page {data.page} of {data.pages}
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={data.page <= 1}
                    onClick={() => setPage((value) => value - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={data.page >= data.pages}
                    onClick={() => setPage((value) => value + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </Card>
    </div>
  );
}
