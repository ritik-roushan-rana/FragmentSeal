"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Download,
  FileText,
  FlaskConical,
  Grid3x3,
  KeyRound,
  QrCode,
  RotateCcw,
  ShieldOff,
  Trash2,
} from "lucide-react";
import { useState } from "react";

import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Alert, Modal, Mono, Skeleton, StatRow, Tabs } from "@/components/ui/misc";
import { EmptyRow, Table, Td, Th, Tr } from "@/components/ui/table";
import { ApiError, apiBlob, apiDelete, apiPost, downloadBlob } from "@/lib/api";
import type { DocumentDetail, Paginated, VerificationLog } from "@/lib/types";
import { useApiResource, useAuthedImage } from "@/lib/use-api";
import { formatDateTime, relativeTime, shortHash } from "@/lib/utils";

type TabId = "preview" | "fragments" | "verifications" | "sandbox";

const tamperModes = [
  { id: "edit_text", label: "Replace the text in a cell" },
  { id: "overlay_block", label: "Redact a cell with a solid block" },
  { id: "strip_watermark", label: "Paint over the authentication footer" },
  { id: "replace_page", label: "Delete a page" },
];

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params?.id;

  const {
    data: document,
    error: loadError,
    reload,
  } = useApiResource<DocumentDetail>(id ? `/documents/${id}` : null, {
    errorMessage: "Could not load that document.",
  });
  const { data: logs } = useApiResource<Paginated<VerificationLog>>(
    id ? `/verify/logs?document_id=${id}&page_size=50` : null,
    { auth: false },
  );

  const [actionError, setActionError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>("preview");
  const [pageIndex, setPageIndex] = useState(0);

  const qrUrl = useAuthedImage(id ? `/documents/${id}/qr` : null);
  const pageUrl = useAuthedImage(id ? `/documents/${id}/pages/${pageIndex}?dpi=120` : null);

  const [revokeOpen, setRevokeOpen] = useState(false);
  const [revokeReason, setRevokeReason] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const [tamperMode, setTamperMode] = useState("edit_text");
  const [tamperCell, setTamperCell] = useState(6);
  const [tamperPage, setTamperPage] = useState(0);
  const [replacement, setReplacement] = useState("Second Class - Pass");
  const [tamperNote, setTamperNote] = useState<string | null>(null);

  const error = loadError ?? actionError;

  async function download(path: string, filename: string) {
    const { blob } = await apiBlob(path);
    downloadBlob(blob, filename);
  }

  async function revoke() {
    if (!id) return;
    setBusy(true);
    try {
      await apiPost(`/documents/${id}/revoke`, { reason: revokeReason.trim() });
      setRevokeOpen(false);
      setRevokeReason("");
      reload();
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not revoke the document.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function reinstate() {
    if (!id) return;
    setBusy(true);
    try {
      await apiPost(`/documents/${id}/reinstate`);
      reload();
    } catch (caught) {
      setActionError(caught instanceof ApiError ? caught.message : "Could not reinstate it.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!id) return;
    setBusy(true);
    try {
      await apiDelete(`/documents/${id}`);
      router.push("/admin/documents");
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not delete the document.",
      );
      setBusy(false);
    }
  }

  async function runSandbox() {
    if (!id || !document) return;
    setBusy(true);
    setTamperNote(null);
    try {
      const { blob, response } = await apiBlob(`/documents/${id}/tamper-sandbox`, {
        method: "POST",
        body: {
          mode: tamperMode,
          page_index: tamperPage,
          cell_index: tamperCell,
          replacement,
        },
      });
      downloadBlob(blob, `tampered-${document.id.slice(0, 8)}.pdf`);
      setTamperNote(
        response.headers.get("X-Tamper-Description") ??
          "An altered copy was downloaded. Upload it on the verify page to see detection.",
      );
    } catch (caught) {
      setActionError(
        caught instanceof ApiError ? caught.message : "Could not build the test copy.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (error && !document) {
    return (
      <AdminShell title="Document">
        <AdminError message={error} />
      </AdminShell>
    );
  }

  if (!document) {
    return (
      <AdminShell title="Document">
        <div className="space-y-4">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      </AdminShell>
    );
  }

  const pageFragments = document.fragments.filter(
    (fragment) => fragment.page_index === pageIndex,
  );

  return (
    <AdminShell
      title={document.document_name}
      description={`Issued ${formatDateTime(document.created_at)} · ${document.fragment_count} fragments across ${document.page_count} page(s)`}
      action={
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/documents">
            <Button variant="ghost" size="sm" icon={<ArrowLeft className="size-3.5" />}>
              Register
            </Button>
          </Link>
          <Button
            variant="outline"
            size="sm"
            icon={<Download className="size-3.5" />}
            onClick={() =>
              download(`/documents/${document.id}/download`, `secured-${document.document_name}`)
            }
          >
            Secured PDF
          </Button>
          {document.status === "revoked" ? (
            <Button
              size="sm"
              variant="secondary"
              loading={busy}
              icon={<RotateCcw className="size-3.5" />}
              onClick={reinstate}
            >
              Reinstate
            </Button>
          ) : (
            <Button
              size="sm"
              variant="danger"
              icon={<ShieldOff className="size-3.5" />}
              onClick={() => setRevokeOpen(true)}
            >
              Revoke
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-5">
        {error ? <AdminError message={error} /> : null}

        {document.status === "revoked" ? (
          <Alert tone="warn" title="This document is revoked">
            {document.revoked_reason} · withdrawn {formatDateTime(document.revoked_at)}. It will
            verify as <strong>revoked</strong> even though its contents are intact.
          </Alert>
        ) : null}

        <div className="grid gap-5 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Issuance record"
              description="What was signed, and with which key."
              icon={<FileText className="size-4" />}
              action={<Badge tone={verdictTone[document.status] ?? "neutral"}>{document.status}</Badge>}
            />
            <CardBody>
              <div className="grid gap-x-8 sm:grid-cols-2">
                <div>
                  <StatRow label="Document ID" value={document.id} mono />
                  <StatRow label="Subject" value={document.subject || "—"} />
                  <StatRow label="Issuer" value={document.issuer || "—"} />
                  <StatRow
                    label="Owner"
                    value={`${document.owner_name ?? "—"}${
                      document.owner_email ? ` · ${document.owner_email}` : ""
                    }`}
                  />
                  <StatRow label="Pages" value={document.page_count} />
                </div>
                <div>
                  <StatRow label="Algorithm" value={document.algorithm} />
                  <StatRow
                    label="Signing key"
                    value={
                      <span className="inline-flex items-center gap-1">
                        <KeyRound className="size-3" />
                        <Mono>{document.key_id ?? "—"}</Mono>
                      </span>
                    }
                  />
                  <StatRow label="Grid" value={`${document.grid_rows}×${document.grid_cols}`} />
                  <StatRow label="Verifications" value={document.verification_count} />
                  <StatRow
                    label="Last verified"
                    value={
                      document.last_verified_at
                        ? relativeTime(document.last_verified_at)
                        : "never"
                    }
                  />
                </div>
              </div>

              <div className="mt-4 space-y-3">
                <div className="rounded-lg bg-surface-muted p-3">
                  <p className="text-[10px] uppercase tracking-wide text-muted">Merkle root</p>
                  <p className="mt-1 font-mono text-[11px] break-all">{document.merkle_root}</p>
                </div>
                <div className="rounded-lg bg-surface-muted p-3">
                  <p className="text-[10px] uppercase tracking-wide text-muted">
                    Signature over the root
                  </p>
                  <p className="mt-1 font-mono text-[11px] break-all">{document.signature}</p>
                </div>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="QR stamp"
              description="Carries ID, root, timestamp and signature."
              icon={<QrCode className="size-4" />}
            />
            <CardBody>
              {qrUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={qrUrl}
                  alt={`QR code for ${document.document_name}`}
                  className="mx-auto w-44 rounded-lg border border-[var(--border)] bg-white p-2"
                />
              ) : (
                <Skeleton className="mx-auto size-44" />
              )}
              <div className="mt-4 flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1"
                  icon={<Download className="size-3.5" />}
                  onClick={() => download(`/documents/${document.id}/qr`, `qr-${document.id}.png`)}
                >
                  PNG
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="flex-1"
                  onClick={() =>
                    download(
                      `/documents/${document.id}/original`,
                      `original-${document.document_name}`,
                    )
                  }
                >
                  Original
                </Button>
              </div>
              {document.qr_payload ? (
                <div className="mt-4">
                  <StatRow label="Payload version" value={`v${document.qr_payload.version}`} />
                  <StatRow
                    label="Signature (preview)"
                    value={<Mono>{document.qr_payload.signature_preview}</Mono>}
                  />
                </div>
              ) : null}
            </CardBody>
          </Card>
        </div>

        <Card>
          <div className="border-b border-[var(--border)] px-5 py-3">
            <Tabs<TabId>
              value={tab}
              onChange={setTab}
              tabs={[
                { id: "preview", label: "Page preview & grid" },
                { id: "fragments", label: "Fragment hashes", count: document.fragment_count },
                { id: "verifications", label: "Verifications", count: logs?.total ?? 0 },
                { id: "sandbox", label: "Tamper sandbox" },
              ]}
            />
          </div>

          {tab === "preview" ? (
            <CardBody>
              {document.page_count > 1 ? (
                <div className="mb-3 flex gap-1 rounded-lg bg-surface-muted p-1">
                  {Array.from({ length: document.page_count }, (_, index) => (
                    <button
                      key={index}
                      onClick={() => setPageIndex(index)}
                      className={`cursor-pointer rounded-md px-2.5 py-1 text-xs font-medium ${
                        pageIndex === index
                          ? "bg-surface text-foreground shadow-[var(--shadow-sm)]"
                          : "text-muted hover:text-foreground"
                      }`}
                    >
                      Page {index + 1}
                    </button>
                  ))}
                </div>
              ) : null}

              <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                {pageUrl ? (
                  <div className="relative mx-auto w-fit">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={pageUrl}
                      alt={`${document.document_name}, page ${pageIndex + 1}`}
                      className="block max-w-full rounded-md shadow-[var(--shadow-md)]"
                    />
                    <div className="pointer-events-none absolute inset-0">
                      {pageFragments.map((fragment) => (
                        <span
                          key={fragment.fragment_index}
                          className="absolute border border-dashed border-brand/40"
                          style={{
                            left: `${(fragment.x0 / fragment.page_width) * 100}%`,
                            top: `${(fragment.y0 / fragment.page_height) * 100}%`,
                            width: `${((fragment.x1 - fragment.x0) / fragment.page_width) * 100}%`,
                            height: `${((fragment.y1 - fragment.y0) / fragment.page_height) * 100}%`,
                          }}
                        >
                          <span className="absolute top-0.5 left-0.5 rounded bg-brand/80 px-1 font-mono text-[9px] text-white">
                            {fragment.cell_index}
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>
                ) : (
                  <Skeleton className="mx-auto h-[600px] w-[420px]" />
                )}
              </div>
              <p className="mt-3 flex items-center gap-2 text-[11px] text-muted">
                <Grid3x3 className="size-3.5" />
                Dashed cells are the fragments that were hashed. The footer band below them is
                reserved for the QR and watermark stamp and is excluded from hashing.
              </p>
            </CardBody>
          ) : null}

          {tab === "fragments" ? (
            <Table>
              <thead>
                <tr>
                  <Th>#</Th>
                  <Th>Page</Th>
                  <Th>Cell</Th>
                  <Th>Box (pt)</Th>
                  <Th>Chars</Th>
                  <Th>Fragment hash</Th>
                  <Th>Text hash</Th>
                  <Th>Raster hash</Th>
                  <Th>Preview</Th>
                </tr>
              </thead>
              <tbody>
                {document.fragments.map((fragment) => (
                  <Tr key={fragment.fragment_index}>
                    <Td className="tabular-nums">{fragment.fragment_index}</Td>
                    <Td className="tabular-nums">{fragment.page_index + 1}</Td>
                    <Td className="font-mono text-xs">
                      {fragment.cell_index} (r{fragment.row}c{fragment.col})
                    </Td>
                    <Td className="font-mono text-[10px] whitespace-nowrap text-muted">
                      {fragment.x0.toFixed(0)},{fragment.y0.toFixed(0)} →{" "}
                      {fragment.x1.toFixed(0)},{fragment.y1.toFixed(0)}
                    </Td>
                    <Td className="tabular-nums">{fragment.char_count}</Td>
                    <Td>
                      <Mono>{shortHash(fragment.fragment_hash, 8, 6)}</Mono>
                    </Td>
                    <Td>
                      <Mono>{shortHash(fragment.text_hash, 6, 4)}</Mono>
                    </Td>
                    <Td>
                      <Mono>{shortHash(fragment.raster_hash, 6, 4)}</Mono>
                    </Td>
                    <Td className="max-w-[18rem] truncate text-xs text-muted">
                      {fragment.text_preview || "—"}
                    </Td>
                  </Tr>
                ))}
              </tbody>
            </Table>
          ) : null}

          {tab === "verifications" ? (
            <Table>
              <thead>
                <tr>
                  <Th>When</Th>
                  <Th>Verifier</Th>
                  <Th>Verdict</Th>
                  <Th>Score</Th>
                  <Th>Affected fragments</Th>
                  <Th>File</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {!logs?.items.length ? (
                  <EmptyRow colSpan={7}>This document has not been verified yet.</EmptyRow>
                ) : (
                  logs.items.map((log) => (
                    <Tr key={log.id}>
                      <Td className="whitespace-nowrap text-xs">
                        <span title={formatDateTime(log.timestamp)}>
                          {relativeTime(log.timestamp)}
                        </span>
                      </Td>
                      <Td className="text-xs text-muted">{log.verifier}</Td>
                      <Td>
                        <Badge tone={verdictTone[log.result] ?? "neutral"}>{log.result}</Badge>
                      </Td>
                      <Td className="tabular-nums">{log.tamper_score}</Td>
                      <Td className="tabular-nums">{log.fragments_modified}</Td>
                      <Td className="max-w-[12rem] truncate text-xs">{log.file_name}</Td>
                      <Td>
                        <Link href={`/verify/result/${log.id}`}>
                          <Button size="sm" variant="ghost">
                            Report
                          </Button>
                        </Link>
                      </Td>
                    </Tr>
                  ))
                )}
              </tbody>
            </Table>
          ) : null}

          {tab === "sandbox" ? (
            <CardBody className="space-y-4">
              <Alert tone="info" title="Detection test">
                This builds an altered <em>copy</em> of the secured PDF so you can confirm the
                pipeline catches it. The issued file and its register entry are untouched.
                Download the copy, then upload it on the verify page.
              </Alert>

              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Alteration" htmlFor="mode">
                  <Select
                    id="mode"
                    value={tamperMode}
                    onChange={(event) => setTamperMode(event.target.value)}
                  >
                    {tamperModes.map((mode) => (
                      <option key={mode.id} value={mode.id}>
                        {mode.label}
                      </option>
                    ))}
                  </Select>
                </Field>

                <Field label="Page" htmlFor="page">
                  <Select
                    id="page"
                    value={tamperPage}
                    onChange={(event) => setTamperPage(Number(event.target.value))}
                  >
                    {Array.from({ length: document.page_count }, (_, index) => (
                      <option key={index} value={index}>
                        Page {index + 1}
                      </option>
                    ))}
                  </Select>
                </Field>

                {tamperMode !== "replace_page" && tamperMode !== "strip_watermark" ? (
                  <Field label="Grid cell" htmlFor="cell">
                    <Select
                      id="cell"
                      value={tamperCell}
                      onChange={(event) => setTamperCell(Number(event.target.value))}
                    >
                      {Array.from(
                        { length: document.grid_rows * document.grid_cols },
                        (_, index) => (
                          <option key={index} value={index}>
                            Cell {index} (row {Math.floor(index / document.grid_cols)}, col{" "}
                            {index % document.grid_cols})
                          </option>
                        ),
                      )}
                    </Select>
                  </Field>
                ) : null}

                {tamperMode === "edit_text" ? (
                  <Field label="Replacement text" htmlFor="replacement">
                    <Input
                      id="replacement"
                      value={replacement}
                      onChange={(event) => setReplacement(event.target.value)}
                    />
                  </Field>
                ) : null}
              </div>

              {tamperNote ? <Alert tone="warn">{tamperNote}</Alert> : null}

              <div className="flex flex-wrap gap-2">
                <Button
                  loading={busy}
                  icon={<FlaskConical className="size-4" />}
                  onClick={runSandbox}
                >
                  Build and download the altered copy
                </Button>
                <Link href="/verify">
                  <Button variant="outline">Go to the verifier</Button>
                </Link>
              </div>
            </CardBody>
          ) : null}
        </Card>

        <Card className="border-[var(--bad)]/25">
          <CardHeader
            title="Delete this record"
            description="Removes the register entry, its fragment hashes and the stored files. Documents already distributed will then verify as 'not recognised'. Prefer revocation."
            icon={<Trash2 className="size-4" />}
            action={
              <Button variant="danger" size="sm" onClick={() => setDeleteOpen(true)}>
                Delete
              </Button>
            }
          />
        </Card>
      </div>

      <Modal
        open={revokeOpen}
        onClose={() => setRevokeOpen(false)}
        title="Revoke this document"
        description="Verification will report 'revoked' from now on, with the reason you give here."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevokeOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={busy}
              disabled={revokeReason.trim().length < 3}
              onClick={revoke}
            >
              Revoke document
            </Button>
          </>
        }
      >
        <Field
          label="Reason"
          hint="Shown to anyone who verifies this document."
          htmlFor="reason"
        >
          <Input
            id="reason"
            value={revokeReason}
            onChange={(event) => setRevokeReason(event.target.value)}
            placeholder="e.g. Superseded by a corrected certificate"
          />
        </Field>
      </Modal>

      <Modal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title="Delete this document record?"
        description="This cannot be undone."
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={busy} onClick={remove}>
              Delete permanently
            </Button>
          </>
        }
      >
        <p className="text-sm text-muted">
          <strong className="text-foreground">{document.document_name}</strong> and its{" "}
          {document.fragment_count} fragment hashes will be removed, along with the secured PDF,
          the original and the QR image. Copies already in circulation will no longer be
          recognised.
        </p>
      </Modal>
    </AdminShell>
  );
}
