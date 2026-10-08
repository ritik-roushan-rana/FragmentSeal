"use client";

import { RefreshCw, ScrollText } from "lucide-react";
import { useMemo, useState } from "react";

import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Mono, Skeleton } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import type { AuditEntry, Paginated } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { formatDateTime, relativeTime, shortHash } from "@/lib/utils";

export default function AuditLogsPage() {
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);

  const path = useMemo(() => {
    const query = new URLSearchParams({ page: String(page), page_size: "25" });
    if (action) query.set("action", action);
    return `/audit-logs?${query}`;
  }, [action, page]);

  const { data, error, reload } = useApiResource<Paginated<AuditEntry>>(path, {
    errorMessage: "Could not load the audit trail.",
  });

  return (
    <AdminShell
      title="Audit trail"
      description="Append-only record of every privileged action and verification."
      action={
        <div className="flex gap-2">
          <Select
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            className="h-9 w-auto text-xs"
            aria-label="Filter by action"
          >
            <option value="">All actions</option>
            {(data?.actions ?? []).map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </Select>
          <Button variant="ghost" size="sm" icon={<RefreshCw className="size-3.5" />} onClick={reload}>
            Refresh
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        {error ? <AdminError message={error} /> : null}

        <Card>
          <CardHeader
            title="Events"
            description={data ? `${data.total} entr${data.total === 1 ? "y" : "ies"}` : undefined}
            icon={<ScrollText className="size-4" />}
          />
          {!data ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 8 }, (_, index) => (
                <Skeleton key={index} className="h-9 w-full" />
              ))}
            </div>
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>When</Th>
                    <Th>Action</Th>
                    <Th>Actor</Th>
                    <Th>Entity</Th>
                    <Th>Detail</Th>
                    <Th>IP</Th>
                  </tr>
                </thead>
                <tbody>
                  {!data.items.length ? (
                    <EmptyRow colSpan={6}>No audit entries for this filter.</EmptyRow>
                  ) : (
                    data.items.map((entry) => (
                      <Tr key={entry.id}>
                        <Td className="whitespace-nowrap text-xs">
                          <span title={formatDateTime(entry.timestamp)}>
                            {relativeTime(entry.timestamp)}
                          </span>
                        </Td>
                        <Td>
                          <Mono>{entry.action}</Mono>
                        </Td>
                        <Td className="text-xs text-muted">{entry.user_email ?? "system"}</Td>
                        <Td className="text-xs">
                          {entry.entity_type ? (
                            <span className="text-muted">
                              {entry.entity_type} · <Mono>{shortHash(entry.entity_id, 8, 4)}</Mono>
                            </span>
                          ) : (
                            "—"
                          )}
                        </Td>
                        <Td className="max-w-[26rem] text-xs break-words text-muted">
                          {entry.detail || "—"}
                        </Td>
                        <Td className="font-mono text-[10px] text-muted">
                          {entry.ip_address ?? "—"}
                        </Td>
                      </Tr>
                    ))
                  )}
                </tbody>
              </Table>

              {data.pages > 1 ? (
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
    </AdminShell>
  );
}
