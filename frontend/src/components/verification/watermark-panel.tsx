"use client";

import { Badge } from "@/components/ui/badge";
import { Mono, StatRow } from "@/components/ui/misc";
import { Progress } from "@/components/ui/progress";
import type { VerificationResult } from "@/lib/types";

export function WatermarkPanel({
  watermark,
  markerIssues,
  fragmentTotal,
}: {
  watermark: VerificationResult["watermark"];
  markerIssues: number;
  fragmentTotal: number;
}) {
  const recovered = watermark.bits_checked
    ? (watermark.bits_matched / watermark.bits_checked) * 100
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={watermark.valid ? "ok" : "bad"}>
          DWT payload {watermark.valid ? "intact" : "broken"}
        </Badge>
        <Badge tone={markerIssues === 0 ? "ok" : "bad"}>
          {markerIssues === 0
            ? "All fragment markers valid"
            : `${markerIssues}/${fragmentTotal} fragment markers failed`}
        </Badge>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="text-muted">Bits recovered from the carrier</span>
          <span className="font-semibold tabular-nums">
            {watermark.bits_matched}/{watermark.bits_checked}
          </span>
        </div>
        <Progress value={recovered} tone={watermark.valid ? "ok" : "bad"} />
      </div>

      <div>
        <StatRow label="Bit-error rate" value={watermark.bit_error_rate.toFixed(4)} />
        <StatRow label="Tolerance (semi-fragile)" value={watermark.tolerance.toFixed(2)} />
        <StatRow label="Expected payload prefix" value={<Mono>{watermark.expected_prefix || "—"}</Mono>} />
        <StatRow
          label="Recovered payload prefix"
          value={<Mono>{watermark.recovered_prefix || "—"}</Mono>}
        />
      </div>

      {watermark.note ? (
        <p className="rounded-lg bg-[var(--warn-soft)] px-3 py-2 text-xs text-[var(--warn)]">
          {watermark.note}
        </p>
      ) : (
        <p className="text-xs leading-relaxed text-muted">
          The carrier embeds the first {watermark.bits_checked} bits of the Merkle root in the
          mid-frequency wavelet coefficients of the footer stamp. Mild requantisation leaves it
          readable; rewriting the stamp does not.
        </p>
      )}
    </div>
  );
}
