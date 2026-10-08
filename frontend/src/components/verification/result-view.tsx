"use client";

import {
  ArrowLeft,
  Blocks,
  Download,
  FileText,
  Grid3x3,
  KeyRound,
  Mail,
  QrCode,
  Waves,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { TamperScoreGauge } from "@/components/charts/charts";
import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Alert, Modal, Mono, StatRow, Tabs } from "@/components/ui/misc";
import { CheckTile } from "@/components/verification/check-grid";
import { FragmentTable } from "@/components/verification/fragment-table";
import { MerklePanel } from "@/components/verification/merkle-panel";
import { QrPanel } from "@/components/verification/qr-panel";
import { TamperHeatmap } from "@/components/verification/tamper-heatmap";
import { VerdictBanner } from "@/components/verification/verdict-banner";
import { VerificationTimeline } from "@/components/verification/timeline";
import { WatermarkPanel } from "@/components/verification/watermark-panel";
import { API, ApiError, apiBlob, apiPost, downloadBlob } from "@/lib/api";
import type { FragmentAnalysis, VerificationResult } from "@/lib/types";
import { formatDateTime, shortHash } from "@/lib/utils";

type TabId = "heatmap" | "fragments" | "crypto" | "timeline";

export function ResultView({
  result,
  backHref = "/verify",
}: {
  result: VerificationResult;
  backHref?: string;
}) {
  const [tab, setTab] = useState<TabId>(
    result.heatmap.length ? "heatmap" : "fragments",
  );
  const [selected, setSelected] = useState<FragmentAnalysis | null>(null);
  const [emailOpen, setEmailOpen] = useState(false);
  const [emailTo, setEmailTo] = useState("");
  const [emailNote, setEmailNote] = useState("");
  const [emailState, setEmailState] = useState<{
    tone: "ok" | "bad";
    message: string;
  } | null>(null);
  const [emailBusy, setEmailBusy] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const { fragments, signature, merkle, watermark, qr, document: doc } = result;
  const damaged = fragments.modified + fragments.missing + fragments.added;

  async function downloadReport() {
    setDownloading(true);
    try {
      const { blob } = await apiBlob(`/verify/logs/${result.log_id}/report`, { auth: false });
      downloadBlob(blob, `verification-report-${result.log_id.slice(0, 8)}.pdf`);
    } finally {
      setDownloading(false);
    }
  }

  async function sendEmail() {
    setEmailBusy(true);
    setEmailState(null);
    try {
      const response = await apiPost<{ sent: boolean; reason: string | null }>(
        `/verify/logs/${result.log_id}/email`,
        { to: emailTo.trim(), note: emailNote.trim() || null },
        { auth: false },
      );
      setEmailState(
        response.sent
          ? { tone: "ok", message: `Report sent to ${emailTo}.` }
          : {
              tone: "bad",
              message: response.reason ?? "The mail server rejected the message.",
            },
      );
    } catch (caught) {
      setEmailState({
        tone: "bad",
        message: caught instanceof ApiError ? caught.message : "Could not send the report.",
      });
    } finally {
      setEmailBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href={backHref}>
          <Button variant="ghost" size="sm" icon={<ArrowLeft className="size-3.5" />}>
            Verify another document
          </Button>
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            icon={<Mail className="size-3.5" />}
            onClick={() => setEmailOpen(true)}
          >
            E-mail report
          </Button>
          <Button
            size="sm"
            loading={downloading}
            icon={<Download className="size-3.5" />}
            onClick={downloadReport}
          >
            Download PDF report
          </Button>
        </div>
      </div>

      <VerdictBanner
        verdict={result.result}
        score={result.tamper_score}
        fileName={result.file.name}
        verifiedAt={result.verified_at}
        durationMs={result.duration_ms}
        revokedReason={result.revoked_reason}
      />

      <div className="grid gap-4 lg:grid-cols-4">
        <CheckTile
          label="QR payload"
          ok={qr.found}
          detail={
            qr.found
              ? `Decoded optically from the footer stamp · document ${shortHash(
                  qr.payload?.document_id,
                  8,
                  4,
                )}`
              : "No QR code could be read from this file."
          }
        />
        <CheckTile
          label="Digital signature"
          ok={signature.valid}
          detail={
            signature.valid
              ? `${signature.algorithm} signature over the Merkle root validates against key ${signature.key_id}.`
              : "The signature does not validate against any registered public key."
          }
        />
        <CheckTile
          label="Merkle integrity"
          ok={merkle.match}
          detail={
            merkle.match
              ? `All ${merkle.leaf_count} leaves rebuild the signed root.`
              : `Recomputed root differs from the signed root across ${merkle.leaf_count} leaves.`
          }
        />
        <CheckTile
          label="Invisible watermark"
          ok={watermark.valid}
          detail={`DWT payload: ${watermark.bits_matched}/${watermark.bits_checked} bits recovered (BER ${watermark.bit_error_rate}).`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Tamper score" icon={<Grid3x3 className="size-4" />} />
          <CardBody>
            <TamperScoreGauge score={result.tamper_score} />
            <div className="mt-2 grid grid-cols-2 gap-2 text-center">
              {[
                ["Intact", fragments.intact, "ok"],
                ["Modified", fragments.modified, "bad"],
                ["Missing", fragments.missing, "warn"],
                ["Added", fragments.added, "accent"],
              ].map(([label, value, tone]) => (
                <div key={label as string} className="rounded-lg bg-surface-muted px-2 py-2">
                  <p className="text-lg font-semibold tabular-nums">{value as number}</p>
                  <Badge tone={tone as "ok"}>{label as string}</Badge>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader
            title="Document identity"
            description={
              doc.registered
                ? "Matched against the issuing authority's register."
                : "Not found in the register — the embedded manifest was used instead."
            }
            icon={<FileText className="size-4" />}
            action={
              <Badge tone={verdictTone[doc.status] ?? "neutral"}>{doc.status}</Badge>
            }
          />
          <CardBody>
            <div className="grid gap-x-8 sm:grid-cols-2">
              <div>
                <StatRow label="Document ID" value={doc.id ?? "—"} mono />
                <StatRow label="Document name" value={doc.name ?? "—"} />
                <StatRow label="Subject" value={doc.subject ?? "—"} />
                <StatRow label="Issuer" value={doc.issuer ?? "—"} />
              </div>
              <div>
                <StatRow label="Issued at" value={formatDateTime(doc.issued_at)} />
                <StatRow label="Pages" value={result.file.page_count} />
                <StatRow label="Fragments checked" value={fragments.total} />
                <StatRow label="File SHA-256" value={<Mono>{shortHash(result.file.sha256, 14, 8)}</Mono>} />
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      <Card>
        <div className="border-b border-[var(--border)] px-5 py-3">
          <Tabs<TabId>
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "heatmap", label: "Tamper visualisation", count: result.heatmap.length },
              { id: "fragments", label: "Fragment analysis", count: damaged },
              { id: "crypto", label: "QR, signature & watermark" },
              { id: "timeline", label: "Verification timeline", count: result.timeline.length },
            ]}
          />
        </div>

        {tab === "heatmap" ? (
          <CardBody>
            {damaged === 0 ? (
              <Alert tone="ok" title="Nothing to highlight" className="mb-4">
                Every fragment reproduced its issued hash. The grid below shows the
                fragmentation scheme that was checked.
              </Alert>
            ) : null}
            <TamperHeatmap
              logId={result.log_id}
              pageCount={result.file.page_count}
              regions={result.heatmap}
              analysis={fragments.analysis}
              onSelect={setSelected}
              selectedCell={selected?.cell_index ?? null}
            />
          </CardBody>
        ) : null}

        {tab === "fragments" ? (
          <FragmentTable
            analysis={fragments.analysis}
            onSelect={setSelected}
            selectedCell={selected?.cell_index ?? null}
          />
        ) : null}

        {tab === "crypto" ? (
          <CardBody className="grid gap-6 lg:grid-cols-3">
            <section>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <QrCode className="size-4 text-brand" /> QR payload
              </h4>
              <QrPanel
                payload={qr.payload}
                found={qr.found}
                manifestPresent={result.manifest_present}
                baselineSource={result.baseline_source}
              />
            </section>
            <section>
              <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <Blocks className="size-4 text-brand" /> Merkle verification
              </h4>
              <MerklePanel merkle={merkle} />
            </section>
            <section className="space-y-6">
              <div>
                <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <Waves className="size-4 text-brand" /> Watermark
                </h4>
                <WatermarkPanel
                  watermark={watermark}
                  markerIssues={fragments.marker_issues}
                  fragmentTotal={fragments.total}
                />
              </div>
              <div>
                <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold">
                  <KeyRound className="size-4 text-brand" /> Signature
                </h4>
                <StatRow label="Algorithm" value={signature.algorithm} />
                <StatRow label="Key ID" value={<Mono>{signature.key_id ?? "—"}</Mono>} />
                <StatRow
                  label="Signature"
                  value={<Mono>{signature.signature_preview || "—"}</Mono>}
                />
                <StatRow
                  label="Signed root"
                  value={<Mono>{shortHash(signature.signed_root, 14, 8)}</Mono>}
                />
              </div>
            </section>
          </CardBody>
        ) : null}

        {tab === "timeline" ? (
          <CardBody>
            <VerificationTimeline steps={result.timeline} />
          </CardBody>
        ) : null}
      </Card>

      <Modal
        open={Boolean(selected)}
        onClose={() => setSelected(null)}
        title={`Fragment ${selected?.cell_index ?? ""} · page ${(selected?.page_index ?? 0) + 1}`}
        description={selected?.reason}
      >
        {selected ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Badge tone={verdictTone[selected.status] ?? "neutral"}>{selected.status}</Badge>
              <Badge tone={selected.text_changed ? "bad" : "ok"}>
                text {selected.text_changed ? "changed" : "unchanged"}
              </Badge>
              <Badge tone={selected.visual_changed ? "bad" : "ok"}>
                pixels {selected.visual_changed ? "changed" : "unchanged"}
              </Badge>
              <Badge tone={verdictTone[selected.marker_status] ?? "neutral"}>
                marker {selected.marker_status}
              </Badge>
            </div>

            <div>
              <StatRow label="Fragment index" value={selected.fragment_index} />
              <StatRow label="Issued hash" value={<Mono>{selected.expected_hash ?? "—"}</Mono>} />
              <StatRow
                label="Recomputed hash"
                value={<Mono>{selected.actual_hash ?? "—"}</Mono>}
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-[var(--border)] bg-surface-muted p-3">
                <p className="text-[10px] uppercase tracking-wide text-muted">As issued</p>
                <p className="mt-1 text-xs leading-relaxed break-words">
                  {selected.expected_preview || <span className="text-muted">(no text)</span>}
                </p>
              </div>
              <div
                className={`rounded-lg border p-3 ${
                  selected.status === "intact"
                    ? "border-[var(--border)] bg-surface-muted"
                    : "border-[var(--bad)]/30 bg-[var(--bad-soft)]"
                }`}
              >
                <p className="text-[10px] uppercase tracking-wide opacity-80">In this file</p>
                <p className="mt-1 text-xs leading-relaxed break-words">
                  {selected.actual_preview || <span className="opacity-60">(no text)</span>}
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        open={emailOpen}
        onClose={() => {
          setEmailOpen(false);
          setEmailState(null);
        }}
        title="E-mail this verification report"
        description="The PDF report is attached. Requires SMTP to be configured on the backend."
        footer={
          <>
            <Button variant="ghost" onClick={() => setEmailOpen(false)}>
              Cancel
            </Button>
            <Button loading={emailBusy} disabled={!emailTo.includes("@")} onClick={sendEmail}>
              Send report
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {emailState ? <Alert tone={emailState.tone}>{emailState.message}</Alert> : null}
          <Field label="Recipient" htmlFor="email-to">
            <Input
              id="email-to"
              type="email"
              value={emailTo}
              onChange={(event) => setEmailTo(event.target.value)}
              placeholder="registrar@university.example"
            />
          </Field>
          <Field label="Note" hint="Optional message included in the e-mail body." htmlFor="email-note">
            <Input
              id="email-note"
              value={emailNote}
              onChange={(event) => setEmailNote(event.target.value)}
            />
          </Field>
          <p className="text-[11px] text-muted">
            Report ID <Mono>{result.log_id}</Mono> · API{" "}
            <Mono>{API.replace(/^https?:\/\//, "")}</Mono>
          </p>
        </div>
      </Modal>
    </div>
  );
}
