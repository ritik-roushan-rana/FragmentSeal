import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Mono } from "@/components/ui/misc";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "The cryptography behind QR-linked fragmented watermarking: fragment hashing, Merkle " +
    "trees, digital signatures, semi-fragile DWT watermarks and tamper localisation.",
};

const sections = [
  {
    id: "fragmentation",
    title: "1 · Fragmentation",
    body: (
      <>
        <p>
          Each page is divided into a grid over its content area — six rows by two columns by
          default. The bottom <Mono>96pt</Mono> of every page is a reserved footer band that is
          deliberately <em>excluded</em> from fragmentation. That exclusion is what makes the
          scheme work: the QR code has to contain the Merkle root, but the root cannot be known
          until the page has been hashed. Keeping the stamp outside the hashed area breaks the
          circularity.
        </p>
        <p>
          A fragment is identified by <Mono>(page, cell)</Mono> and carries its bounding box in
          PDF points, which is what later lets a failed hash be drawn as a rectangle on the page.
        </p>
      </>
    ),
  },
  {
    id: "hashing",
    title: "2 · Two digests per fragment",
    body: (
      <>
        <p>Every fragment is hashed twice, because tampering takes more than one form:</p>
        <ul>
          <li>
            <strong>Text digest</strong> — SHA-256 over the fragment&apos;s characters, rebuilt
            from their positions and normalised (NFKC, collapsed whitespace). Character-level
            reconstruction means the digest does not shift just because a word extractor grouped
            glyphs differently.
          </li>
          <li>
            <strong>Raster digest</strong> — SHA-256 over the rendered pixels of the cell at
            100 dpi, quantised to 16 grey levels. This catches edited images, signatures,
            stamps and solid-block redactions that leave the text layer untouched, while the
            quantisation absorbs antialiasing noise.
          </li>
        </ul>
        <p>
          The fragment hash is <Mono>SHA-256(text_hash | raster_hash)</Mono>; those are the
          Merkle leaves.
        </p>
      </>
    ),
  },
  {
    id: "merkle",
    title: "3 · Merkle tree and root",
    body: (
      <>
        <p>
          Leaves are hashed with a <Mono>0x00</Mono> prefix and internal nodes with{" "}
          <Mono>0x01</Mono>, so a leaf pre-image can never be confused with a node pre-image — a
          classic second-preimage defence. An odd level duplicates its last node.
        </p>
        <p>
          The payoff is the inclusion proof: any single fragment can be proved to belong to the
          signed root using only <Mono>log₂(n)</Mono> sibling hashes. The verification report
          shows that audit path for the first fragment that failed.
        </p>
      </>
    ),
  },
  {
    id: "signature",
    title: "4 · Digital signature",
    body: (
      <>
        <p>
          Only the root is signed. The default is ECDSA on P-256 with SHA-256, serialised as raw{" "}
          <Mono>r‖s</Mono>, which is 64 bytes — small enough to keep the QR at roughly 77 modules
          and genuinely scannable with a phone. RSA-PSS with SHA-256 is also supported for
          deployments that mandate RSA, at the cost of a much denser QR.
        </p>
        <p>
          Verification walks every registered public key, so rotating the issuing key does not
          invalidate documents already in circulation.
        </p>
      </>
    ),
  },
  {
    id: "watermark",
    title: "5 · Fragmented invisible watermarking",
    body: (
      <>
        <p>Two layers, with different jobs:</p>
        <ul>
          <li>
            <strong>Per-fragment markers.</strong> Each grid cell is stamped with a 2pt,
            near-white marker <Mono>&lt;WM|cell|hash12&gt;</Mono> carrying the first 12 hex digits
            of that cell&apos;s own text digest. Because the evidence is distributed across the
            page rather than concentrated in the footer, a region that is cut out or replaced can
            be shown to be inconsistent on its own. Marker ink is excluded from the hashed text,
            so stamping cannot perturb what it is attesting to.
          </li>
          <li>
            <strong>Semi-fragile DWT payload.</strong> A low-contrast carrier image in the footer
            band holds the first 128 bits of the Merkle root, embedded by quantisation index
            modulation in the level-2 horizontal detail sub-band of a Haar wavelet decomposition.
            Coefficient positions come from a key-derived permutation. The step size tolerates the
            rounding of an encode/decode round trip and mild requantisation, but a rewritten stamp
            destroys the payload — which is exactly the &quot;semi-fragile&quot; property.
          </li>
        </ul>
      </>
    ),
  },
  {
    id: "verification",
    title: "6 · Verification",
    body: (
      <>
        <p>An uploaded file is asked four independent questions:</p>
        <ul>
          <li>
            <strong>Provenance</strong> — can a QR payload be decoded from the footer, or a
            manifest read from the PDF metadata, and does it name a document in the register?
          </li>
          <li>
            <strong>Authority</strong> — does the signature over the claimed root validate
            against a registered public key?
          </li>
          <li>
            <strong>Integrity</strong> — do recomputed fragment hashes rebuild that same root, and
            if not, which leaves moved?
          </li>
          <li>
            <strong>Watermark</strong> — does the DWT payload still decode, and does each region
            still carry its matching marker?
          </li>
        </ul>
        <p>
          The verdict combines them. A genuine signature over a document whose fragments no longer
          match is the signature of tampering: <em>tampered</em>, not <em>invalid</em>. A file
          that is cryptographically perfect but withdrawn by its issuer reads as{" "}
          <em>revoked</em>. A file carrying no verification data at all is <em>not recognised</em>{" "}
          rather than &quot;fake&quot;, because there is nothing to compare it against.
        </p>
      </>
    ),
  },
  {
    id: "limits",
    title: "Honest limits",
    body: (
      <ul>
        <li>
          Fragmentation localises to a grid cell, not to a word. A finer grid gives finer
          localisation at the cost of more hashes — the grid is configurable.
        </li>
        <li>
          The raster digest is reproducible because protection and verification render with the
          same library and version. Across a renderer upgrade, raster digests would need
          recomputing; text digests are unaffected.
        </li>
        <li>
          Printing and re-scanning a document is not supported: the raster digest and the DWT
          payload are both destroyed by the print-scan channel. Verification operates on the
          digital file.
        </li>
        <li>
          Text below 3pt is treated as marker ink and excluded from text hashing. Such content is
          still covered by the raster digest.
        </li>
      </ul>
    ),
  },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-16">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">How it works</h1>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
        The whole design answers one question: when a document fails verification, can you say{" "}
        <em>where</em>? Everything below exists to make that answer precise and provable.
      </p>

      <nav className="mt-8 flex flex-wrap gap-2">
        {sections.map((section) => (
          <a
            key={section.id}
            href={`#${section.id}`}
            className="rounded-lg border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:text-foreground"
          >
            {section.title}
          </a>
        ))}
      </nav>

      <div className="mt-10 space-y-6">
        {sections.map((section) => (
          <Card key={section.id} id={section.id} className="scroll-mt-24">
            <CardHeader title={section.title} />
            <CardBody>
              <div className="space-y-3 text-sm leading-relaxed text-muted [&_li]:ml-4 [&_li]:list-disc [&_strong]:text-foreground [&_ul]:space-y-2">
                {section.body}
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card className="mt-8">
        <CardBody className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold">See it on a real file</h3>
            <p className="mt-1 text-xs text-muted">
              The verifier shows every step of the pipeline with its intermediate values.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href="/verify">
              <Button>Verify a document</Button>
            </Link>
            <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
              <Button variant="outline">API reference</Button>
            </a>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
