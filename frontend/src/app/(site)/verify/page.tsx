"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  FileSearch,
  History,
  Info,
  Loader2,
  QrCode,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/input";
import { Alert, Mono } from "@/components/ui/misc";
import { UploadZone } from "@/components/verification/upload-zone";
import { ApiError, apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { VerificationResult } from "@/lib/types";

const stages = [
  "Reading the file",
  "Decoding the QR stamp",
  "Extracting the invisible watermark",
  "Re-hashing every fragment",
  "Rebuilding the Merkle tree",
  "Checking the signature",
];

export default function VerifyPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [files, setFiles] = useState<File[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function onVerify() {
    if (!files.length) return;
    setBusy(true);
    setError(null);
    setStage(0);

    // The backend runs the whole pipeline in one request; this walks the
    // stage labels so the wait communicates what is actually happening.
    const ticker = window.setInterval(
      () => setStage((value) => Math.min(value + 1, stages.length - 1)),
      550,
    );

    const body = new FormData();
    body.append("file", files[0]);
    if (documentId.trim()) body.append("document_id", documentId.trim());
    body.append("source", "upload");

    try {
      const result = await apiPost<VerificationResult>("/verify", body, {
        auth: Boolean(user),
      });
      router.push(`/verify/result/${result.log_id}`);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Verification failed. Is the backend running?",
      );
      setBusy(false);
    } finally {
      window.clearInterval(ticker);
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Verify a document</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            Upload a PDF that was issued through this platform. Nothing is required of you —
            the file carries its own proof. You get the verdict, the cryptographic evidence and
            a map of any altered regions.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/verify/scan">
            <Button variant="outline" icon={<ScanLine className="size-4" />}>
              Scan QR instead
            </Button>
          </Link>
          <Link href="/verify/history">
            <Button variant="ghost" icon={<History className="size-4" />}>
              History
            </Button>
          </Link>
        </div>
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Upload the document"
            description="The PDF is hashed fragment by fragment and compared with the issued record."
            icon={<FileSearch className="size-4" />}
          />
          <CardBody className="space-y-4">
            {error ? <Alert tone="bad" title="Verification error">{error}</Alert> : null}

            <UploadZone files={files} onChange={setFiles} disabled={busy} />

            <Field
              label="Document ID (optional)"
              hint="Only needed if the QR stamp is unreadable and the file has no embedded manifest."
              htmlFor="doc-id"
            >
              <Input
                id="doc-id"
                value={documentId}
                onChange={(event) => setDocumentId(event.target.value)}
                placeholder="e.g. 7f3a1c42-9b5e-4d18-8c21-0a7e5b9d4f66"
                disabled={busy}
              />
            </Field>

            {busy ? (
              <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                <div className="relative mb-4 h-1.5 overflow-hidden rounded-full bg-neutral-soft">
                  <span className="animate-scan absolute inset-x-0 h-1.5 bg-gradient-to-r from-transparent via-brand to-transparent" />
                </div>
                <ul className="space-y-1.5">
                  {stages.map((label, index) => (
                    <li
                      key={label}
                      className={`flex items-center gap-2 text-xs ${
                        index <= stage ? "text-foreground" : "text-muted/60"
                      }`}
                    >
                      {index < stage ? (
                        <ShieldCheck className="size-3.5 text-[var(--ok)]" />
                      ) : index === stage ? (
                        <Loader2 className="size-3.5 animate-spin text-brand" />
                      ) : (
                        <span className="size-3.5" />
                      )}
                      {label}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <Button
              size="lg"
              className="w-full"
              disabled={!files.length}
              loading={busy}
              icon={<ShieldCheck className="size-4" />}
              onClick={onVerify}
            >
              {busy ? "Verifying…" : "Verify document"}
            </Button>
          </CardBody>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title="What gets checked" icon={<Info className="size-4" />} />
            <CardBody>
              <ul className="space-y-3 text-xs leading-relaxed text-muted">
                <li>
                  <span className="font-semibold text-foreground">QR payload</span> — document
                  ID, Merkle root, issuance timestamp and signature, decoded optically from the
                  footer stamp.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Signature</span> — validated
                  against the authority&apos;s published public key.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Fragment hashes</span> — text
                  and rendered pixels re-hashed per grid cell.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Merkle root</span> — rebuilt
                  from the recomputed leaves and compared with the signed root.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Watermarks</span> — the
                  semi-fragile DWT payload and every per-fragment marker.
                </li>
                <li>
                  <span className="font-semibold text-foreground">Revocation</span> — whether
                  the issuer has since withdrawn the document.
                </li>
              </ul>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="No file to hand?" icon={<QrCode className="size-4" />} />
            <CardBody>
              <p className="text-xs leading-relaxed text-muted">
                A QR scan alone proves the authority issued that Merkle root for that document
                ID, and whether it is still valid. It cannot prove the paper in front of you
                still matches — that needs the file.
              </p>
              <Link href="/verify/scan" className="mt-3 block">
                <Button variant="secondary" size="sm" className="w-full">
                  Open the QR scanner
                </Button>
              </Link>
            </CardBody>
          </Card>

          <p className="px-1 text-[11px] leading-relaxed text-muted">
            Files are kept only so the result page can render the tamper overlay. Max upload{" "}
            <Mono>25 MB</Mono>.
          </p>
        </div>
      </div>
    </div>
  );
}
