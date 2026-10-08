import Link from "next/link";
import {
  ArrowRight,
  BadgeCheck,
  Blocks,
  FileSearch,
  Fingerprint,
  Grid3x3,
  KeyRound,
  QrCode,
  ScanLine,
  ShieldCheck,
  Waves,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";

const pipeline = [
  {
    Icon: Grid3x3,
    title: "Fragment",
    body: "Each page's content area is split into a 6×2 grid. A fragment is the unit at which tampering is located.",
  },
  {
    Icon: Fingerprint,
    title: "Hash",
    body: "Every fragment gets a SHA-256 digest over its normalised text and over its rendered pixels, so edits to type and to images both register.",
  },
  {
    Icon: Blocks,
    title: "Build the tree",
    body: "Fragment hashes become the leaves of a Merkle tree. One root commits to the whole document, and any leaf can be proved against it.",
  },
  {
    Icon: KeyRound,
    title: "Sign",
    body: "The root is signed with the issuer's ECDSA P-256 key (RSA-PSS is also supported). Only the root is signed, so the signature stays small.",
  },
  {
    Icon: Waves,
    title: "Watermark",
    body: "A semi-fragile DWT payload goes into the footer carrier, and a per-fragment marker is stamped invisibly into every grid cell.",
  },
  {
    Icon: QrCode,
    title: "Publish",
    body: "Document ID, root, timestamp and signature are encoded into the QR stamp, making the proof travel with the paper.",
  },
];

const audiences = [
  {
    title: "Universities",
    body: "Degree certificates and transcripts that an employer can check in seconds, with grade fields pinpointed if altered.",
  },
  {
    title: "Government registries",
    body: "Licences, permits and land records with a published revocation list and a full audit trail of every check.",
  },
  {
    title: "Enterprises",
    body: "Contracts, invoices and letters of employment, bulk-issued and verified through an API or the browser.",
  },
];

export default function HomePage() {
  return (
    <>
      <section className="relative overflow-hidden border-b border-[var(--border)]">
        <div className="grid-pattern absolute inset-0 opacity-40" />
        <div className="absolute -top-40 left-1/2 size-[36rem] -translate-x-1/2 rounded-full bg-brand/10 blur-3xl" />
        <div className="relative mx-auto max-w-7xl px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-3xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-surface px-3 py-1 text-xs font-medium text-muted">
              <ShieldCheck className="size-3.5 text-brand" />
              Fragment-level tamper detection · Merkle proofs · QR-linked
            </span>
            <h1 className="mt-6 text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
              Prove a document is unchanged — and show exactly where it was not.
            </h1>
            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">
              Most verification tells you a file&apos;s hash no longer matches. FragmentSeal
              splits the document into fragments, commits them to a Merkle tree, and embeds
              invisible per-region watermarks — so a verifier sees the altered paragraph
              highlighted on the page, not just a failed checksum.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/verify">
                <Button size="lg" icon={<FileSearch className="size-4" />}>
                  Verify a document
                </Button>
              </Link>
              <Link href="/verify/scan">
                <Button size="lg" variant="outline" icon={<ScanLine className="size-4" />}>
                  Scan a QR code
                </Button>
              </Link>
              <Link href="/login">
                <Button size="lg" variant="ghost">
                  Issuer sign in <ArrowRight className="size-4" />
                </Button>
              </Link>
            </div>
          </div>

          <div className="mx-auto mt-16 grid max-w-4xl gap-4 sm:grid-cols-3">
            {[
              ["6×2", "fragments per page"],
              ["SHA-256", "per fragment, text + pixels"],
              ["128-bit", "DWT watermark payload"],
            ].map(([stat, label]) => (
              <Card key={stat} className="text-center">
                <CardBody>
                  <p className="text-2xl font-semibold tracking-tight">{stat}</p>
                  <p className="mt-1 text-xs text-muted">{label}</p>
                </CardBody>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="max-w-2xl">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            What happens when a document is issued
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Six steps run on upload. Together they make the document self-describing: the proof
            of what it said when issued travels inside the file and on its face.
          </p>
        </div>

        <ol className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {pipeline.map(({ Icon, title, body }, index) => (
            <li key={title}>
              <Card className="h-full transition-shadow hover:shadow-[var(--shadow-md)]">
                <CardBody>
                  <div className="flex items-center gap-3">
                    <span className="grid size-9 place-items-center rounded-lg bg-brand-soft text-brand">
                      <Icon className="size-4.5" />
                    </span>
                    <span className="font-mono text-xs text-muted">
                      0{index + 1}
                    </span>
                    <h3 className="text-sm font-semibold">{title}</h3>
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-muted">{body}</p>
                </CardBody>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      <section className="border-y border-[var(--border)] bg-surface">
        <div className="mx-auto grid max-w-7xl gap-10 px-4 py-20 lg:grid-cols-2 lg:items-center">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              A forged grade changes one fragment — and only that fragment
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-muted">
              Because the signature covers the Merkle root rather than each page, an attacker
              who edits the body cannot re-sign it. Re-hashing the uploaded file rebuilds the
              tree; the leaf that no longer matches identifies the grid cell, and the cell
              carries its own coordinates. The verifier gets a rectangle on the page.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                "Text edits, pasted blocks and painted-over redactions are all caught — text and raster digests are independent.",
                "Each cell also carries an invisible marker derived from its own text, so a cut-out region is detectable on its own.",
                "The semi-fragile DWT payload survives re-saving a PDF but not a rewritten stamp.",
                "Revocation is checked at verification time, so a withdrawn-but-intact document never reads as valid.",
              ].map((item) => (
                <li key={item} className="flex gap-2.5 text-sm text-muted">
                  <BadgeCheck className="mt-0.5 size-4 shrink-0 text-[var(--ok)]" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <Card className="overflow-hidden">
            <div className="border-b border-[var(--border)] bg-surface-muted px-4 py-2.5">
              <p className="font-mono text-[11px] text-muted">
                verification report · fragment analysis
              </p>
            </div>
            <CardBody className="space-y-2">
              {[
                { cell: 0, status: "intact" },
                { cell: 1, status: "intact" },
                { cell: 2, status: "intact" },
                { cell: 6, status: "modified" },
                { cell: 7, status: "intact" },
              ].map(({ cell, status }) => (
                <div
                  key={cell}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 ${
                    status === "modified"
                      ? "bg-[var(--bad-soft)] text-[var(--bad)]"
                      : "bg-surface-muted"
                  }`}
                >
                  <span className="font-mono text-[11px]">cell {String(cell).padStart(2, "0")}</span>
                  <span className="text-[11px] font-semibold uppercase tracking-wide">
                    {status}
                  </span>
                  <span className="ml-auto font-mono text-[10px] opacity-70">
                    {status === "modified" ? "text + pixels differ" : "hash reproduced"}
                  </span>
                </div>
              ))}
              <p className="pt-2 text-[11px] text-muted">
                Merkle root mismatch localised to 1 of 12 fragments · tamper score 24.6/100
              </p>
            </CardBody>
          </Card>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20">
        <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">Who it is for</h2>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {audiences.map(({ title, body }) => (
            <Card key={title}>
              <CardBody>
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-muted">{body}</p>
              </CardBody>
            </Card>
          ))}
        </div>

        <Card className="mt-10 overflow-hidden border-brand/30 bg-gradient-to-br from-brand/5 to-[var(--accent)]/5">
          <CardBody className="flex flex-wrap items-center justify-between gap-6 py-8">
            <div className="max-w-lg">
              <h3 className="text-lg font-semibold tracking-tight">
                Try it with a document you have in hand
              </h3>
              <p className="mt-1.5 text-sm text-muted">
                Upload a PDF to see the full report — QR payload, signature check, Merkle
                rebuild, fragment analysis and the tamper heatmap.
              </p>
            </div>
            <Link href="/verify">
              <Button size="lg" icon={<FileSearch className="size-4" />}>
                Open the verifier
              </Button>
            </Link>
          </CardBody>
        </Card>
      </section>
    </>
  );
}
