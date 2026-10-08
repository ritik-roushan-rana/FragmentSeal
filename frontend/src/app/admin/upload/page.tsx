"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CheckCircle2,
  Layers,
  ShieldCheck,
  Upload,
  XCircle,
} from "lucide-react";
import { useState } from "react";

import { AdminError, AdminShell } from "@/components/layout/admin-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Alert, Mono, StatRow, Tabs } from "@/components/ui/misc";
import { UploadZone } from "@/components/verification/upload-zone";
import { ApiError, apiPost } from "@/lib/api";
import type { DocumentDetail, DocumentSummary } from "@/lib/types";
import { shortHash } from "@/lib/utils";

const steps = [
  "Fragment the content area into a 6×2 grid per page",
  "Stamp an invisible per-fragment watermark marker in every cell",
  "Hash each fragment: normalised text + rendered pixels (SHA-256)",
  "Fold the fragment hashes into a Merkle tree and take the root",
  "Sign the root with the issuing key (ECDSA P-256)",
  "Embed the 128-bit DWT watermark payload in the footer carrier",
  "Encode ID, root, timestamp and signature into the QR stamp",
  "Write the verification manifest into the PDF metadata",
];

type Mode = "single" | "bulk";

interface BulkOutcome {
  issued: DocumentSummary[];
  failed: { file: string; error: string }[];
  issued_count: number;
  failed_count: number;
}

export default function UploadPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("single");
  const [files, setFiles] = useState<File[]>([]);
  const [subject, setSubject] = useState("");
  const [issuer, setIssuer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [issued, setIssued] = useState<DocumentDetail | null>(null);
  const [bulk, setBulk] = useState<BulkOutcome | null>(null);

  async function protectSingle() {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    setIssued(null);
    try {
      const query = new URLSearchParams();
      if (subject.trim()) query.set("subject", subject.trim());
      if (issuer.trim()) query.set("issuer", issuer.trim());
      const body = new FormData();
      body.append("file", files[0]);
      const result = await apiPost<DocumentDetail>(
        `/documents${query.toString() ? `?${query}` : ""}`,
        body,
      );
      setIssued(result);
      setFiles([]);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not protect that document.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function protectBulk() {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    setBulk(null);
    try {
      const query = new URLSearchParams();
      if (issuer.trim()) query.set("issuer", issuer.trim());
      const body = new FormData();
      files.forEach((file) => body.append("files", file));
      const result = await apiPost<BulkOutcome>(
        `/documents/bulk${query.toString() ? `?${query}` : ""}`,
        body,
      );
      setBulk(result);
      setFiles([]);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The bulk upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminShell
      title="Issue protected documents"
      description="Upload a PDF; the platform returns a tamper-evident version with a QR stamp."
    >
      <div className="grid gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          {error ? <AdminError message={error} /> : null}

          <Card>
            <CardHeader
              title="Source document"
              description="Text-based PDFs give the finest localisation; scanned PDFs are still covered by the per-fragment raster hash."
              icon={<Upload className="size-4" />}
              action={
                <Tabs<Mode>
                  value={mode}
                  onChange={(next) => {
                    setMode(next);
                    setFiles([]);
                    setIssued(null);
                    setBulk(null);
                  }}
                  tabs={[
                    { id: "single", label: "Single" },
                    { id: "bulk", label: "Bulk" },
                  ]}
                />
              }
            />
            <CardBody className="space-y-4">
              <UploadZone
                files={files}
                onChange={setFiles}
                multiple={mode === "bulk"}
                disabled={busy}
                hint={
                  mode === "bulk"
                    ? "Select several PDFs — each is protected independently"
                    : "PDF only · up to 25 MB"
                }
              />

              <div className="grid gap-4 sm:grid-cols-2">
                {mode === "single" ? (
                  <Field
                    label="Subject"
                    hint="Who the document is about — shown on verification."
                    htmlFor="subject"
                  >
                    <Input
                      id="subject"
                      value={subject}
                      onChange={(event) => setSubject(event.target.value)}
                      placeholder="e.g. Aarav Sharma"
                      disabled={busy}
                    />
                  </Field>
                ) : null}
                <Field
                  label="Issuer"
                  hint="Defaults to your organisation."
                  htmlFor="issuer"
                >
                  <Input
                    id="issuer"
                    value={issuer}
                    onChange={(event) => setIssuer(event.target.value)}
                    placeholder="e.g. National Institute of Technology"
                    disabled={busy}
                  />
                </Field>
              </div>

              <Button
                size="lg"
                className="w-full"
                disabled={!files.length}
                loading={busy}
                icon={<ShieldCheck className="size-4" />}
                onClick={mode === "single" ? protectSingle : protectBulk}
              >
                {busy
                  ? "Protecting…"
                  : mode === "single"
                    ? "Protect and issue"
                    : `Protect ${files.length || ""} document${files.length === 1 ? "" : "s"}`}
              </Button>
            </CardBody>
          </Card>

          {issued ? (
            <Card className="animate-fade-up border-[var(--ok)]/30">
              <CardHeader
                title="Document issued"
                description="The secured PDF now carries its own proof."
                icon={<CheckCircle2 className="size-4" />}
                action={
                  <Link href={`/admin/documents/${issued.id}`}>
                    <Button size="sm">
                      Open record <ArrowRight className="size-3.5" />
                    </Button>
                  </Link>
                }
              />
              <CardBody>
                <div className="grid gap-x-8 sm:grid-cols-2">
                  <div>
                    <StatRow label="Document ID" value={issued.id} mono />
                    <StatRow label="Name" value={issued.document_name} />
                    <StatRow label="Pages" value={issued.page_count} />
                    <StatRow label="Fragments" value={issued.fragment_count} />
                  </div>
                  <div>
                    <StatRow
                      label="Merkle root"
                      value={<Mono>{shortHash(issued.merkle_root, 14, 8)}</Mono>}
                    />
                    <StatRow label="Algorithm" value={issued.algorithm} />
                    <StatRow label="Key ID" value={<Mono>{issued.key_id ?? "—"}</Mono>} />
                    <StatRow
                      label="Grid"
                      value={`${issued.grid_rows}×${issued.grid_cols} per page`}
                    />
                  </div>
                </div>
              </CardBody>
            </Card>
          ) : null}

          {bulk ? (
            <Card className="animate-fade-up">
              <CardHeader
                title="Bulk result"
                description={`${bulk.issued_count} issued · ${bulk.failed_count} failed`}
                icon={<Layers className="size-4" />}
              />
              <CardBody className="space-y-2">
                {bulk.issued.map((document) => (
                  <div
                    key={document.id}
                    className="flex flex-wrap items-center gap-3 rounded-lg bg-[var(--ok-soft)] px-3 py-2"
                  >
                    <CheckCircle2 className="size-4 shrink-0 text-[var(--ok)]" />
                    <span className="min-w-0 flex-1 truncate text-sm">
                      {document.document_name}
                    </span>
                    <Mono>{shortHash(document.merkle_root, 10, 6)}</Mono>
                    <Link href={`/admin/documents/${document.id}`}>
                      <Button size="sm" variant="ghost">
                        Open
                      </Button>
                    </Link>
                  </div>
                ))}
                {bulk.failed.map((failure) => (
                  <div
                    key={failure.file}
                    className="flex items-start gap-3 rounded-lg bg-[var(--bad-soft)] px-3 py-2"
                  >
                    <XCircle className="mt-0.5 size-4 shrink-0 text-[var(--bad)]" />
                    <div className="min-w-0">
                      <p className="truncate text-sm">{failure.file}</p>
                      <p className="text-xs text-[var(--bad)]">{failure.error}</p>
                    </div>
                  </div>
                ))}
                {bulk.issued_count ? (
                  <Button
                    variant="secondary"
                    className="mt-2 w-full"
                    onClick={() => router.push("/admin/documents")}
                  >
                    Go to the document register
                  </Button>
                ) : null}
              </CardBody>
            </Card>
          ) : null}
        </div>

        <div className="space-y-5">
          <Card>
            <CardHeader title="What protection does" />
            <CardBody>
              <ol className="space-y-2.5">
                {steps.map((step, index) => (
                  <li key={step} className="flex gap-2.5 text-xs leading-relaxed text-muted">
                    <span className="grid size-5 shrink-0 place-items-center rounded bg-brand-soft font-mono text-[10px] text-brand">
                      {index + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Before you upload" />
            <CardBody>
              <Alert tone="info">
                The source file is kept so you can compare it later, and the secured version is
                what you distribute. Verification always runs against the secured file.
              </Alert>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge tone="brand">PDF only</Badge>
                <Badge tone="neutral">≤ 25 MB</Badge>
                <Badge tone="neutral">96pt footer reserved</Badge>
              </div>
            </CardBody>
          </Card>
        </div>
      </div>
    </AdminShell>
  );
}
