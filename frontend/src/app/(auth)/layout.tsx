import Link from "next/link";

import { Brand } from "@/components/layout/brand";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-brand to-[var(--accent)] p-10 text-white lg:flex">
        <div className="grid-pattern absolute inset-0 opacity-15" />
        <Link href="/" className="relative">
          <span className="text-sm font-semibold tracking-tight">FragmentSeal</span>
        </Link>
        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight tracking-tight">
            A changed line should not need a lawyer to prove.
          </h2>
          <p className="mt-4 text-sm leading-relaxed text-white/85">
            Every issued document is split into a grid of fragments. Each fragment is hashed
            with SHA-256, the hashes are folded into a Merkle tree, and the root is signed and
            published in the QR stamp. Re-hash the file and the tree tells you not just
            <em> whether</em> it changed — but <em>where</em>.
          </p>
          <dl className="mt-8 grid grid-cols-3 gap-4 text-center">
            {[
              ["SHA-256", "per fragment"],
              ["Merkle", "integrity proof"],
              ["DWT", "watermark"],
            ].map(([term, detail]) => (
              <div key={term} className="rounded-lg bg-white/10 px-3 py-3 backdrop-blur-sm">
                <dt className="text-sm font-semibold">{term}</dt>
                <dd className="mt-0.5 text-[10px] uppercase tracking-wide text-white/70">
                  {detail}
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="relative text-[11px] text-white/60">
          Demonstration platform for universities, registries and enterprises.
        </p>
      </div>

      <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Link href="/" className="lg:hidden">
            <Brand className="mb-8" />
          </Link>
          {children}
        </div>
      </div>
    </div>
  );
}
