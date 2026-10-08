"use client";

import { ArrowDown, Hash } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Mono } from "@/components/ui/misc";
import type { VerificationResult } from "@/lib/types";
import { shortHash } from "@/lib/utils";

export function MerklePanel({ merkle }: { merkle: VerificationResult["merkle"] }) {
  const proof = merkle.proof_demo ?? {};
  const path = proof.path ?? [];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-[var(--border)] bg-surface-muted p-3">
          <p className="text-[10px] uppercase tracking-wide text-muted">Signed root (from QR)</p>
          <p className="mt-1 font-mono text-[11px] break-all">{merkle.signed_root || "—"}</p>
        </div>
        <div
          className={`rounded-lg border p-3 ${
            merkle.match
              ? "border-[var(--ok)]/30 bg-[var(--ok-soft)]"
              : "border-[var(--bad)]/30 bg-[var(--bad-soft)]"
          }`}
        >
          <p className="text-[10px] uppercase tracking-wide opacity-80">Recomputed root</p>
          <p className="mt-1 font-mono text-[11px] break-all">{merkle.recomputed_root || "—"}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={merkle.match ? "ok" : "bad"}>
          {merkle.match ? "Roots identical" : "Roots differ"}
        </Badge>
        <Badge tone="neutral">{merkle.leaf_count} leaves</Badge>
        {proof.proof_valid !== undefined ? (
          <Badge tone={proof.proof_valid ? "ok" : "bad"}>
            Inclusion proof {proof.proof_valid ? "verified" : "failed"}
          </Badge>
        ) : null}
      </div>

      {path.length ? (
        <div>
          <p className="mb-2 text-xs text-muted">
            Audit path for fragment{" "}
            <span className="font-semibold text-foreground">#{proof.fragment_index}</span>
            {proof.is_tampered_fragment
              ? " — the first fragment that failed, shown with the sibling hashes that fold it into the issued root."
              : " — recomputing the issued root from a single leaf and its siblings."}
          </p>
          <ol className="space-y-1.5">
            <li className="flex items-center gap-2 rounded-lg bg-brand-soft px-3 py-2">
              <Hash className="size-3.5 shrink-0 text-brand" />
              <span className="text-[10px] uppercase tracking-wide text-muted">Leaf</span>
              <Mono className="ml-auto">{shortHash(proof.leaf_hash, 14, 8)}</Mono>
            </li>
            {path.map((step, index) => (
              <li key={index} className="flex items-center gap-2">
                <ArrowDown className="size-3 shrink-0 text-muted" />
                <div className="flex flex-1 items-center gap-2 rounded-lg bg-surface-muted px-3 py-2">
                  <span className="text-[10px] uppercase tracking-wide text-muted">
                    level {index + 1} · sibling {step.position}
                  </span>
                  <Mono className="ml-auto">{shortHash(step.hash, 14, 8)}</Mono>
                </div>
              </li>
            ))}
            <li className="flex items-center gap-2">
              <ArrowDown className="size-3 shrink-0 text-muted" />
              <div
                className={`flex flex-1 items-center gap-2 rounded-lg px-3 py-2 ${
                  proof.root_matches_signed_root
                    ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                    : "bg-[var(--bad-soft)] text-[var(--bad)]"
                }`}
              >
                <span className="text-[10px] uppercase tracking-wide">Issued root</span>
                <Mono className="ml-auto">{shortHash(proof.issued_root, 14, 8)}</Mono>
              </div>
            </li>
          </ol>
        </div>
      ) : null}
    </div>
  );
}
