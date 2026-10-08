import Link from "next/link";

import { Brand } from "@/components/layout/brand";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-[var(--border)] bg-surface">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2">
          <Brand />
          <p className="mt-3 max-w-sm text-xs leading-relaxed text-muted">
            Fragment-level SHA-256 hashing, Merkle-tree integrity proofs, ECDSA/RSA
            signatures and semi-fragile DWT watermarks, linked to a scannable QR code so
            that a single altered line can be located on the page.
          </p>
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Verification
          </h4>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <Link href="/verify" className="text-muted hover:text-foreground">
                Upload a document
              </Link>
            </li>
            <li>
              <Link href="/verify/scan" className="text-muted hover:text-foreground">
                Scan a QR code
              </Link>
            </li>
            <li>
              <Link href="/verify/history" className="text-muted hover:text-foreground">
                Verification history
              </Link>
            </li>
          </ul>
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">
            Platform
          </h4>
          <ul className="mt-3 space-y-2 text-sm">
            <li>
              <Link href="/about" className="text-muted hover:text-foreground">
                How it works
              </Link>
            </li>
            <li>
              <Link href="/login" className="text-muted hover:text-foreground">
                Issuer sign in
              </Link>
            </li>
            <li>
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="text-muted hover:text-foreground"
              >
                API reference
              </a>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[var(--border)] px-4 py-4">
        <p className="mx-auto max-w-7xl text-[11px] text-muted">
          FragmentSeal · QR-Linked Fragmented Watermarking for Tamper-Evident Document
          Authentication. Demonstration platform.
        </p>
      </div>
    </footer>
  );
}
