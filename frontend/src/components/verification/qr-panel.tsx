"use client";

import { KeyRound, QrCode } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Mono, StatRow } from "@/components/ui/misc";
import type { QrPayloadInfo } from "@/lib/types";
import { formatDateTime, shortHash } from "@/lib/utils";

export function QrPanel({
  payload,
  found,
  manifestPresent,
  baselineSource,
}: {
  payload: QrPayloadInfo | null;
  found: boolean;
  manifestPresent: boolean;
  baselineSource: string;
}) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={found ? "ok" : "bad"} icon={<QrCode className="size-3" />}>
          {found ? "QR decoded" : "QR not readable"}
        </Badge>
        <Badge tone={manifestPresent ? "ok" : "warn"}>
          {manifestPresent ? "Manifest embedded" : "No embedded manifest"}
        </Badge>
        <Badge tone={baselineSource === "database" ? "ok" : "warn"}>
          Baseline: {baselineSource}
        </Badge>
      </div>

      {payload ? (
        <div>
          <StatRow label="Document ID" value={payload.document_id} mono />
          <StatRow label="Merkle root" value={<Mono>{shortHash(payload.merkle_root, 16, 10)}</Mono>} />
          <StatRow label="Issued at" value={formatDateTime(payload.issued_at)} />
          <StatRow
            label="Signature"
            value={<Mono>{payload.signature_preview || shortHash(payload.signature, 18, 8)}</Mono>}
          />
          <StatRow
            label="Signing key"
            value={
              <span className="inline-flex items-center gap-1">
                <KeyRound className="size-3" />
                <Mono>{payload.key_id || "—"}</Mono>
              </span>
            }
          />
          <StatRow label="Algorithm" value={payload.algorithm} />
          <StatRow label="Payload version" value={`v${payload.version}`} />
        </div>
      ) : (
        <p className="rounded-lg bg-surface-muted px-3 py-6 text-center text-xs text-muted">
          No QR payload was recovered from this file, so the document could not be linked to
          an issuance record optically.
        </p>
      )}
    </div>
  );
}
