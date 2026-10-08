"use client";

import Link from "next/link";
import { ArrowRight, FileStack, Plus, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Mono, Skeleton } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import type { DocumentStatus, DocumentSummary, Paginated } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";
import { formatDateTime, relativeTime, shortHash } from "@/lib/utils";

const statuses: (DocumentStatus | "")[] = ["", "active", "revoked", "processing", "failed"];

export default function DocumentRegisterPage() {
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [status, setStatus] = useState<DocumentStatus | "">("");
  const [page, setPage] = useState(1);

  // Debounce the search box so typing does not fire a request per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  const path = useMemo(() => {
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    if (debounced) query.set("search", debounced);
    if (status) query.set("status", status);
    return `/documents?${query}`;
  }, [debounced, page, status]);

  const { data, error, loading, reload } = useApiResource<Paginated<DocumentSummary>>(path, {
    errorMessage: "Could not load the register.",
  });

  return (
    <AdminShell
      title="Document register"
      description="Every document issued through this platform, with its Merkle root and status."
      action={
        <div className="flex gap-2">
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
      <div className="space-y-4">
        {error ? <AdminError message={error} /> : null}

        <Card>
          <CardHeader
            title="Issued documents"
            description={data ? `${data.total} record(s)` : undefined}
            icon={<FileStack className="size-4" />}
            action={
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted" />
                  <Input
                    value={search}
                    onChange={(event) => {
                      setSearch(event.target.value);
                      setPage(1);
                    }}
                    placeholder="Name, ID, subject or root"
                    className="h-9 w-56 pl-8 text-xs"
                    aria-label="Search documents"
                  />
                </div>
                <Select
                  value={status}
                  onChange={(event) => {
                    setStatus(event.target.value as DocumentStatus | "");
                    setPage(1);
                  }}
                  className="h-9 w-auto text-xs"
                  aria-label="Filter by status"
                >
                  {statuses.map((value) => (
                    <option key={value} value={value}>
                      {value === "" ? "All statuses" : value}
                    </option>
                  ))}
                </Select>
              </div>
            }
          />

          {loading && !data ? (
            <div className="space-y-2 p-5">
              {Array.from({ length: 6 }, (_, index) => (
                <Skeleton key={index} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <Th>Document</Th>
                    <Th>Subject</Th>
                    <Th>Status</Th>
                    <Th>Merkle root</Th>
                    <Th>Pages</Th>
                    <Th>Fragments</Th>
                    <Th>Issued</Th>
                    <Th />
                  </tr>
                </thead>
                <tbody>
                  {!data?.items.length ? (
                    <EmptyRow colSpan={8}>
                      No documents match. Protect one from the upload page to get started.
                    </EmptyRow>
                  ) : (
                    data.items.map((document) => (
                      <Tr key={document.id}>
                        <Td className="max-w-[16rem]">
                          <Link
                            href={`/admin/documents/${document.id}`}
                            className="block truncate font-medium hover:text-brand"
                          >
                            {document.document_name}
                          </Link>
                          <Mono>{shortHash(document.id, 8, 4)}</Mono>
                        </Td>
                        <Td className="max-w-[10rem] truncate text-xs text-muted">
                          {document.subject || "—"}
                        </Td>
                        <Td>
                          <Badge tone={verdictTone[document.status] ?? "neutral"}>
                            {document.status}
                          </Badge>
                        </Td>
                        <Td>
                          <Mono>{shortHash(document.merkle_root, 10, 6)}</Mono>
                        </Td>
                        <Td className="tabular-nums">{document.page_count}</Td>
                        <Td className="tabular-nums">{document.fragment_count}</Td>
                        <Td className="whitespace-nowrap text-xs text-muted">
                          <span title={formatDateTime(document.created_at)}>
                            {relativeTime(document.created_at)}
                          </span>
                        </Td>
                        <Td>
                          <Link href={`/admin/documents/${document.id}`}>
                            <Button size="sm" variant="ghost">
                              Open <ArrowRight className="size-3.5" />
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
    </AdminShell>
  );
}
