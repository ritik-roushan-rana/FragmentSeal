# Architecture

How the system is put together, and why each piece is shaped the way it is.

---

## 1. The problem

Conventional document verification hashes the whole file. One changed byte changes the
hash, so you learn *that* something changed — never *what*. For a transcript where a single
grade was altered, "invalid" is a true but useless answer.

This system makes the proof **spatial**. The document is divided into a grid of fragments,
each fragment is hashed independently, and the hashes are bound together so none can be
substituted or reordered. A failed verification therefore identifies a *region*, and every
fragment stores its own bounding box — so the report can draw a rectangle on the page.

Everything below exists to serve that one property.

---

## 2. System shape

```
┌──────────────────────────────┐        ┌─────────────────────────────────┐
│  Next.js (browser)           │        │  FastAPI (Python)               │
│                              │        │                                 │
│  public   home · verify      │  JWT   │  routes  auth · documents       │
│           scan QR · report   │ ◄────► │          verify · dashboard     │
│  admin    dashboard · issue  │  REST  │          audit                  │
│           register · detail  │        │                                 │
│           analytics · audit  │        │  services  the pipeline         │
└──────────────────────────────┘        └───────────────┬─────────────────┘
                                                        │
                                  ┌─────────────────────┴──────────────────┐
                                  │                                        │
                        ┌─────────▼─────────┐                 ┌────────────▼───────────┐
                        │ SQLAlchemy         │                │ storage/                │
                        │ SQLite / Postgres  │                │  uploads  secured  qr   │
                        │ 6 tables           │                │  reports  keys          │
                        └────────────────────┘                └─────────────────────────┘
```

The frontend holds no secrets and does no cryptography. It renders what the API reports.
Every check — hashes, tree, signature, watermark — happens server-side, which is the only
place the trusted baseline lives.

---

## 3. Issuance pipeline

Orchestrated by [`services/protection.py`](../backend/app/services/protection.py).

```
                       ┌──────────────┐
  original PDF ───────►│ 1 fragment   │  6×2 grid over the content area
                       └──────┬───────┘  footer band (96pt) reserved
                              ▼
                       ┌──────────────┐
                       │ 2 text hash  │  SHA-256(page | cell | normalised text)
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │ 3 stamp      │  <WM|cell|hash12> at 2pt, 96% grey,
                       │   markers    │  one inside every cell
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │ 4 raster     │  render at 100 dpi, crop each cell,
                       │   hash       │  quantise to 16 grey levels, SHA-256
                       └──────┬───────┘
                              ▼
            fragment_hash = SHA-256(text_hash | raster_hash)
                              ▼
                       ┌──────────────┐
                       │ 5 Merkle     │  12 leaves → root
                       │   tree       │
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │ 6 sign root  │  ECDSA P-256 (or RSA-PSS)
                       └──────┬───────┘
                              ▼
              ┌───────────────┴───────────────┐
              ▼                               ▼
     ┌──────────────┐                 ┌──────────────┐
     │ 7 QR code    │                 │ 8 DWT        │  128 bits of the root into
     │   payload    │                 │   watermark  │  Haar level-2 coefficients
     └──────┬───────┘                 └──────┬───────┘
            └───────────────┬───────────────┘
                            ▼
                     ┌──────────────┐
                     │ 9 stamp the  │  QR + carrier + issuance text,
                     │   footer     │  manifest into PDF metadata
                     └──────┬───────┘
                            ▼
                     secured PDF  +  register row  +  12 fragment rows
```

### The circular dependency, and how it is broken

The QR must carry the Merkle root. But placing the QR on the page changes the page, which
changes the root. Two devices resolve this:

**The reserved footer band.** Fragments cover only the area above the bottom `FOOTER_BAND_PT`
(96pt). The QR, the watermark carrier and the issuance text all live in that band, so they
can be added *after* hashing without invalidating a single hash. This is the reason the
constant exists.

**Two-pass marker stamping.** A marker inside a cell contains a hash of that cell — the same
circularity in miniature. So markers carry only the **text** hash, computed before stamping;
the **raster** hash is computed afterwards over the already-marked page. Neither hash can
depend on itself.

### Why two digests per fragment

| Digest | Catches | Blind to |
| --- | --- | --- |
| `text_hash` | edited, inserted or deleted text | image edits, redaction blocks |
| `raster_hash` | image edits, forged signatures, solid-block redactions, anything visible | nothing visible, but needs a stable renderer |

Text is rebuilt from **character positions**, not from `extract_words()`. Word grouping shifts
depending on what sits nearby — including a stamped marker — and a digest that changes for
cosmetic reasons is a digest that cries wolf. Characters at or below 3pt are treated as marker
ink and excluded, which is what makes stamping unable to perturb what it attests to.

Raster hashes quantise to 16 grey levels so sub-pixel antialiasing cannot flip a digest, while
any visible change still does.

---

## 4. Merkle tree

[`services/merkle.py`](../backend/app/services/merkle.py)

```
                       root  ← this is what gets signed
                    ┌────┴────┐
                 n01          n23
               ┌──┴──┐      ┌──┴──┐
             L0     L1    L2     L3        L = SHA-256(0x00 ‖ fragment_hash)
             │      │     │      │         n = SHA-256(0x01 ‖ left ‖ right)
            f0     f1    f2     f3
```

Two design points:

- **Domain separation.** Leaves are prefixed `0x00`, internal nodes `0x01`. Without this an
  attacker could present an internal node as though it were a leaf, since both are 32-byte
  values. The prefixes make the two pre-image spaces disjoint.
- **Inclusion proofs.** Any fragment can be proved against the root with `log₂(n)` sibling
  hashes (≈4 for a 12-leaf tree). The verification report renders that audit path for the
  first failing fragment, which is what turns "the root differs" into a concrete chain of
  hashes a reader can follow.

Odd levels duplicate their last node, Bitcoin-style.

---

## 5. Signatures

[`services/signing.py`](../backend/app/services/signing.py)

Only the root is signed — one signature commits to the entire document.

| Algorithm | Signature size | QR result | Default |
| --- | --- | --- | --- |
| **ES256** (ECDSA P-256, raw `r‖s`) | 64 B → 88 base64 chars | 77 modules, **0.34 mm** per module | ✅ |
| **RSA-PSS-SHA256** (2048-bit) | 256 B → 344 chars | 105 modules, 0.18 mm per module | opt-in |

That table is the whole reason ECDSA is the default. At 0.18 mm per module a phone camera
cannot resolve the QR — the "QR-linked" half of the system stops working. RSA-PSS is fully
implemented and tested; set `SIGN_ALGORITHM=RSA-PSS-SHA256` if a deployment mandates RSA, and
widen `FOOTER_BAND_PT` to keep the stamp scannable.

Keys live in the `signing_keys` table with the private PEM on disk at mode 0600. One key is
active at a time, but **verification tries every registered key**, so rotating the issuing key
never invalidates documents already in circulation.

---

## 6. Watermarking

Two layers with different jobs. [`services/watermark.py`](../backend/app/services/watermark.py)

### Per-fragment markers — the "fragmented" part

Every cell is stamped with `<WM|6|a3f09c12d4e5>`: 2pt text at 96% grey, invisible in practice
but genuinely extractable from the PDF text layer. It carries the first 12 hex digits of
*that cell's own* text hash.

Because the evidence is distributed across the page instead of concentrated in the footer, a
region that is cut out and replaced is inconsistent **on its own** — detectable even if an
attacker strips the QR and the manifest entirely.

### Semi-fragile DWT payload

```
carrier image (256×64, low contrast)
        │
        ▼  2-level Haar wavelet decomposition
   ┌────────────────────────────┐
   │ cA2 │ cH2 ◄── payload here │   128 bits of the Merkle root
   │ cV2 │ cD2                  │   embedded by quantisation index
   ├─────┴──────────────────────┤   modulation, step Δ = 12
   │      level-1 detail        │   positions from a key-derived
   └────────────────────────────┘   pseudo-random permutation
```

Each selected coefficient is nudged to an even or odd multiple of Δ to encode a 0 or a 1.
Δ = 12 is chosen to be large enough to survive the rounding of a PDF encode/decode round trip
and mild requantisation, small enough that rewriting the stamp destroys the payload. That is
precisely what "semi-fragile" means, and it is what distinguishes a legitimately re-saved PDF
from a forged stamp.

Measured bit-error rate through real PDF embedding and extraction: **0.0**. Tests assert it
survives Gaussian noise and dies under an overwrite.

Coefficient positions come from a key seeded with the document ID, so the payload cannot be
located — let alone rewritten — without it.

---

## 7. Verification pipeline

[`services/verifier.py`](../backend/app/services/verifier.py) asks four independent questions.

```
  uploaded PDF
       │
       ├─ 1 PROVENANCE   decode the QR from the footer (300/400/240/500 dpi in turn),
       │                 fall back to the manifest in PDF metadata,
       │                 resolve the document ID against the register
       │
       ├─ 2 AUTHORITY    verify the signature over the claimed root
       │                 against every registered public key
       │
       ├─ 3 INTEGRITY    re-fragment, re-hash, rebuild the tree,
       │                 compare roots — then compare leaf by leaf
       │
       └─ 4 WATERMARK    decode the DWT payload; check every cell's
                         marker against its recomputed text hash
       │
       ▼
   verdict + tamper score + per-fragment analysis + heatmap regions
```

### Baseline resolution

The trusted baseline comes from the **database** when the document ID is in the register. If
it is not — an offline copy, a deleted record — the pipeline falls back to the **manifest
embedded in the file** and says so (`baseline_source: "manifest"`), flagging it as lower trust.
A self-describing file can still be checked for internal consistency; it just cannot prove the
authority ever issued it.

### Verdicts

| Verdict | Condition | What it means |
| --- | --- | --- |
| `authentic` | all fragments intact, root matches, signature and watermark valid, document registered | as issued |
| `tampered` | signature **valid**, but fragments or root do not match | the attacker edited the body and could not re-sign — this is the signature of tampering |
| `invalid` | signature does not validate against any key | forged outright |
| `revoked` | cryptographically perfect, but withdrawn by the issuer | genuine, no longer valid |
| `unknown` | no QR, no manifest, no register entry | unrecognised — not "fake", there is simply nothing to compare against |

The distinction between `tampered` and `invalid` is deliberate. A genuine signature over
content that no longer matches tells you something quite specific about what happened.

### Tamper score

```
score = 100 × ( 0.55 × damaged_fragments / total
              + 0.20 × merkle_mismatch
              + 0.15 × signature_failure
              + 0.10 × watermark_failure )
```

Worked example — one edited cell out of twelve, signature and watermark untouched:

```
0.55 × (1/12) = 0.046
0.20 × 1      = 0.200     (the root no longer matches)
0.15 × 0      = 0
0.10 × 0      = 0
              = 0.246  →  24.6 / 100
```

Weights are configurable in [`core/config.py`](../backend/app/core/config.py).

### Tamper localisation

Each fragment row stores `x0, y0, x1, y1` in PDF points plus the page dimensions. The verifier
emits both absolute and normalised coordinates, so the UI positions overlay boxes as
percentages and the heatmap stays correct at any zoom or render DPI.

---

## 8. Data model

[`db/models.py`](../backend/app/db/models.py)

```
users ──────┬──< documents ──┬──< fragments          one row per grid cell,
            │                │                       with its bounding box
            │                └──< verification_logs   full JSON report retained
            │
            └──< audit_logs                           append-only

signing_keys                                          rotatable, all kept for verification
```

| Table | Why it exists |
| --- | --- |
| `users` | name, email, role (`admin`/`verifier`), bcrypt hash, organisation |
| `documents` | the register: Merkle root, signature, key ID, paths, status, revocation reason |
| `fragments` | the trusted baseline **and** the geometry that makes localisation possible |
| `verification_logs` | every check, with the complete report as JSON so a report can be re-rendered later |
| `audit_logs` | every privileged action — issuance, revocation, deletion, sandbox use, logins |
| `signing_keys` | key registry; old keys stay so rotation is non-breaking |

---

## 9. Security model

| Control | Implementation |
| --- | --- |
| Authentication | JWT access (30 min) + refresh (7 days), typed so a refresh token cannot be used as an access token |
| Password storage | bcrypt, cost 12; inputs over 72 bytes are SHA-256'd first so long passphrases are not silently truncated |
| Role-based access | `require_admin` dependency on every issuing route; **self-registration always creates a verifier**, even if the request body says `admin` |
| Account safety | you cannot disable yourself, and the last active admin cannot be disabled |
| Upload limits | PDF only, `MAX_UPLOAD_MB` enforced while streaming, not after |
| Key handling | private PEMs at mode 0600, never served; the public key is published for independent verification |
| Audit | append-only trail with actor, entity, detail and IP |
| Tamper sandbox | only ever writes a copy, never mutates the issued file, and every use is audited |

### What an attacker cannot do

- **Edit the content** — fragment hashes change, the root changes, and the signature cannot be
  regenerated without the private key.
- **Swap or reorder fragments** — position is bound into the hash (`page|cell|text`) and into
  the tree's leaf ordering.
- **Transplant a valid QR from another document** — the QR carries the document ID and root;
  neither will match the file it is pasted onto.
- **Strip the watermark** — the DWT payload stops decoding and every per-cell marker goes
  missing, both reported.
- **Re-save the PDF and claim corruption** — the semi-fragile design survives a legitimate
  round trip, so "it got re-saved" is not an excuse a forgery can hide behind.

---

## 10. Frontend architecture

```
src/
  app/
    (site)/     public routes — home, about, verify, scan, history, result
    (auth)/     login, register, with a shared split-screen layout
    admin/      dashboard, upload, register, document detail, analytics, audit, users
  components/
    ui/         primitives — button, card, badge, input, table, modal, tabs
    layout/     site header/footer, admin shell, brand, theme toggle
    charts/     Recharts wrappers reading colours from CSS custom properties
    verification/  verdict banner, tamper heatmap, fragment table, Merkle and
                   watermark panels, timeline, upload zone
  lib/
    api.ts      typed fetch client with silent token refresh
    auth.tsx    session context and role guards
    use-api.ts  data-loading hooks
    types.ts    the API contract in TypeScript
```

`(site)` and `(auth)` are route groups — they shape layouts without appearing in URLs.

Two patterns worth noting:

- **State is never set synchronously inside an effect.** `useApiResource` writes state only
  from the fetch's own callbacks, which avoids cascading renders on mount and satisfies
  React's `set-state-in-effect` rule. One hook replaced eight copies of the same
  load-error-loading triple.
- **Theming is token-based.** Every colour is a CSS custom property redefined for dark mode, so
  the charts, the heatmap severity tints and the UI all follow the theme without a JS theme
  object.

---

## 11. Known limits

Stated plainly, because a verification system that overclaims is worse than one that does not.

- **Localisation is to a grid cell, not a word.** A 6×2 grid gives twelve regions per page.
  Raising `FRAGMENT_ROWS`/`FRAGMENT_COLS` sharpens localisation at the cost of more hashes.
- **Raster digests couple to the renderer.** Reproducibility holds because issuance and
  verification both use pypdfium2 at the same version. After a renderer upgrade, raster
  digests would need recomputing. Set `ENABLE_RASTER_HASH=false` to avoid the coupling, at the
  cost of missing image-only edits.
- **Print-and-rescan is out of scope.** That channel destroys both the raster digest and the
  DWT payload. Verification operates on the digital file.
- **Text at or below 3pt is excluded from text hashing**, since that is how marker ink is
  identified. Such content is still covered by the raster digest.
- **The manifest fallback is weaker than the register.** It proves internal consistency, not
  that the authority issued the document. The report labels which baseline was used.
