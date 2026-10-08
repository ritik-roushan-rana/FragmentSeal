<h1 align="center">FragmentSeal</h1>
<p align="center">
  <strong>QR-Linked Fragmented Watermarking for Tamper-Evident Document Authentication</strong><br>
  <sub>Fragment-level SHA-256 · Merkle-tree integrity proofs · ECDSA/RSA signatures · semi-fragile DWT watermarks</sub>
</p>

---

A full-stack platform for issuing and verifying authenticated PDF documents.

Conventional verification hashes the whole file: one changed byte changes the hash, so you
learn *that* a document was altered, never *what*. FragmentSeal splits each page into a grid
of fragments, hashes every fragment independently, binds the hashes into a Merkle tree, signs
the root, and publishes it through a QR code — so verification points at the **exact region**
that was altered and draws it on the page.

```
 ┌──────────────┐     issue      ┌───────────────┐     verify     ┌──────────────┐
 │ original PDF │ ─────────────► │ secured PDF   │ ─────────────► │  verdict +   │
 │              │  fragment,     │ QR + invisible│  re-hash,      │  heatmap of  │
 │              │  hash, sign    │ watermarks    │  rebuild tree  │  what changed│
 └──────────────┘                └───────────────┘                └──────────────┘
```

---

## Contents

- [Quick start](#quick-start) · [See it catch a forgery](#see-it-catch-a-forgery-60-seconds)
- [Project structure](#project-structure) · [How it works](#how-it-works)
- [Configuration](#configuration) · [Tests](#tests) · [Limits](#honest-limits)
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the full technical design
- **[docs/API.md](docs/API.md)** — every endpoint

---

## Quick start

**Requires** Python 3.12+ and Node 20+.

```bash
./scripts/setup.sh    # venv, dependencies, env files, demo data
./scripts/dev.sh      # runs the API and the web app together
```

Or with `make`:

```bash
make setup
make dev
```

| | URL |
| --- | --- |
| Web app | **http://localhost:3000** |
| API | http://127.0.0.1:8000 |
| Interactive API docs | http://127.0.0.1:8000/docs |

**Demo accounts**, created by the seeder:

| Role | Email | Password |
| --- | --- | --- |
| Admin (issuer) | `admin@docauth.dev` | `Admin@12345` |
| Verifier | `verifier@docauth.dev` | `Verify@12345` |

<details>
<summary><strong>Manual setup</strong>, if you would rather not use the scripts</summary>

```bash
# Backend
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python -m app.seed --documents        # schema + demo users + 2 sample documents
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

```bash
# Frontend, in a second terminal
cd frontend
npm install
cp .env.example .env.local
npm run dev
```
</details>

### Other commands

| Command | Does |
| --- | --- |
| `make test` | backend test suite, then frontend types, lint and production build |
| `make backend` / `make frontend` | run one side only |
| `make seed` | re-seed demo accounts and sample documents |
| `make reset` | wipe the database and stored files, then re-seed |
| `make clean` | remove caches, `node_modules` and the venv |

---

## See it catch a forgery (60 seconds)

1. Sign in as the admin and open **Document register → academic-transcript.pdf**
2. Go to the **Tamper sandbox** tab, choose *Replace the text in a cell*, pick a cell, and
   download the altered copy.
   *(The issued document is never touched — the sandbox writes a copy, and every use is audited.)*
3. Open **Verify document** and upload that copy
4. The report comes back:

```
verdict: TAMPERED      tamper score: 24.6 / 100
signature: VALID       merkle: MISMATCH       watermark: VALID
fragments: 11 intact · 1 modified · 0 missing · 0 added
  → page 1, cell 6: text content differs; rendered pixels differ;
    embedded watermark marker does not match recomputed text
```

with that one cell shaded red on the rendered page, its issued and recomputed hashes side by
side, and the Merkle audit path for the failing leaf.

Note what the verdict says: the **signature is still valid**. The attacker edited the body and
could not re-sign it — which is exactly the signature of tampering, and why fragment hashing
is needed on top of a signature.

Try *Redact a cell with a solid block* too: no text changes at all, and it is still caught —
that is the raster digest doing its job.

---

## Project structure

```
.
├── README.md                    you are here
├── Makefile                     make setup | dev | test | seed | reset | clean
├── docs/
│   ├── ARCHITECTURE.md          full technical design, diagrams, threat model
│   └── API.md                   endpoint reference
├── scripts/
│   ├── setup.sh                 one-time install + seed
│   ├── dev.sh                   run both servers together
│   └── test.sh                  all checks
│
├── backend/                     FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── main.py              app factory, CORS, startup
│   │   ├── seed.py              schema + demo accounts + sample documents
│   │   ├── core/
│   │   │   ├── config.py        settings (grid size, DPI, DWT params, weights)
│   │   │   └── security.py      JWT issue/verify, bcrypt
│   │   ├── db/
│   │   │   ├── models.py        6 tables
│   │   │   └── session.py       engine + session factory
│   │   ├── schemas/             Pydantic request/response models
│   │   ├── services/            ← the system lives here
│   │   │   ├── fragmenter.py    PDF → grid cells, text + raster digests
│   │   │   ├── merkle.py        tree, root, inclusion proofs
│   │   │   ├── signing.py       key registry, ECDSA + RSA sign/verify
│   │   │   ├── watermark.py     DWT (QIM) embed + extract
│   │   │   ├── qr.py            payload encode, render, multi-scale decode
│   │   │   ├── pdf_builder.py   marker + footer stamping, manifest, extraction
│   │   │   ├── protection.py    the issuance pipeline
│   │   │   ├── verifier.py      the verification engine
│   │   │   ├── tamper_sim.py    tamper sandbox for demos and tests
│   │   │   ├── report.py        PDF verification report + e-mail
│   │   │   ├── sample_docs.py   demo certificate / transcript generators
│   │   │   └── audit.py         append-only audit logging
│   │   └── api/
│   │       ├── deps.py          current user, role guards, client IP
│   │       └── routes/          auth · documents · verify · dashboard · audit
│   ├── tests/                   42 unit + integration tests
│   ├── storage/                 runtime files (gitignored, created on startup)
│   │   ├── uploads/  secured/  qr/  reports/  keys/
│   └── requirements.txt
│
└── frontend/                    Next.js + TypeScript + Tailwind
    └── src/
        ├── app/
        │   ├── (site)/          home · about · verify · scan · history · result
        │   ├── (auth)/          login · register
        │   └── admin/           dashboard · upload · register · detail
        │                        analytics · audit-logs · users
        ├── components/
        │   ├── ui/              button, card, badge, input, table, modal, tabs
        │   ├── layout/          header, footer, admin shell, theme toggle
        │   ├── charts/          Recharts wrappers, themed via CSS variables
        │   └── verification/    verdict banner, tamper heatmap, fragment table,
        │                        Merkle + watermark panels, timeline, upload zone
        └── lib/
            ├── api.ts           typed client with silent token refresh
            ├── auth.tsx         session context + role guards
            ├── use-api.ts       data-loading hooks
            └── types.ts         the API contract in TypeScript
```

---

## How it works

Short version here; the full treatment with diagrams is in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

### Issuing

| Step | What happens |
| --- | --- |
| **1. Fragment** | Each page's content area is split into a 6×2 grid. The bottom 96pt is a *reserved footer band*, excluded from fragmentation. |
| **2. Hash text** | Per cell: `SHA-256(page \| cell \| normalised text)`, rebuilt from character positions rather than word grouping. |
| **3. Stamp markers** | `<WM\|6\|a3f09c12d4e5>` at 2pt in 96% grey goes inside every cell, carrying that cell's own text hash. |
| **4. Hash pixels** | The marked PDF is rendered at 100 dpi; each cell is cropped, quantised to 16 grey levels and hashed. |
| **5. Merkle tree** | `fragment_hash = SHA-256(text_hash \| raster_hash)` are the leaves; the tree folds them to one root. |
| **6. Sign** | Only the root is signed — ECDSA P-256 by default. |
| **7–9. Publish** | ID + root + timestamp + signature into a QR; 128 bits of the root into a DWT watermark carrier; both stamped into the footer band, with the full manifest written into the PDF metadata. |

**The circular dependency.** The QR must contain the root, but putting the QR on the page
changes the page, which changes the root. The reserved footer band resolves it: fragments
never cover that band, so the stamp can be added after hashing. Markers face the same problem
in miniature and are solved with two passes — markers carry only the text hash (computed
before stamping), and raster hashes are computed after.

**Why two digests.** Text hashing catches edited words; raster hashing catches edited images,
forged signatures and solid-block redactions that leave the text layer untouched. Together
they cover both kinds of forgery.

### Verifying

Four independent questions, fused into one verdict:

| | Question | How |
| --- | --- | --- |
| **Provenance** | Who issued this? | Decode the QR from the footer (retried at several DPIs), fall back to the embedded manifest, resolve the ID against the register |
| **Authority** | Did they sign it? | Verify the signature over the claimed root against every registered key |
| **Integrity** | Is it still what they signed? | Re-fragment, re-hash, rebuild the tree, compare roots — then compare leaf by leaf |
| **Watermark** | Is the stamp genuine? | Decode the DWT payload; check each cell's marker against its recomputed text hash |

| Verdict | Meaning |
| --- | --- |
| `authentic` | Every fragment reproduces its issued hash; root, signature and watermark all check out |
| `tampered` | The signature is **genuine** but the content no longer hashes to the signed root — affected regions are reported with coordinates |
| `invalid` | The signature validates against no registered key |
| `revoked` | Cryptographically intact, but withdrawn by the issuer |
| `unknown` | The file carries no verification data — not "fake", simply nothing to compare against |

```
tamper_score = 100 × ( 0.55 × damaged_fragments/total
                     + 0.20 × merkle_mismatch
                     + 0.15 × signature_failure
                     + 0.10 × watermark_failure )
```

---

## Features

**Admin (issuer)** — JWT login · single and bulk PDF protection · document register with
search and filters · per-document detail with page preview, fragment grid overlay, QR stamp
and full hash table · revoke and reinstate · tamper sandbox · analytics with tamper hotspots ·
audit trail · user and signing-key management

**Verifier** — upload a PDF (no account needed) · camera QR scanner with photo and paste
fallbacks · full report: verdict, tamper score, QR payload, signature check, Merkle rebuild
with inclusion proof, watermark bit-error rate, per-fragment analysis · interactive tamper
heatmap over the submitted pages · downloadable PDF report · e-mail delivery · verification
history

---

## Configuration

Backend — `backend/.env`, template in [`.env.example`](backend/.env.example):

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./storage/docauth.db` | PostgreSQL: `postgresql+psycopg2://user:pass@localhost:5432/qrwatermark` |
| `JWT_SECRET` | dev placeholder | **Change before deploying.** |
| `SIGN_ALGORITHM` | `ES256` | or `RSA-PSS-SHA256` |
| `FRAGMENT_ROWS` / `FRAGMENT_COLS` | `6` / `2` | finer grid = finer localisation, more hashes |
| `FOOTER_BAND_PT` | `96` | reserved band, excluded from hashing |
| `RASTER_DPI` | `100` | render resolution for raster digests |
| `ENABLE_RASTER_HASH` | `true` | `false` = text-only hashing |
| `DWT_WAVELET` / `DWT_ALPHA` / `DWT_BITS` | `haar` / `12` / `128` | watermark parameters |
| `MAX_UPLOAD_MB` | `25` | |
| `SMTP_*` | empty | optional; enables e-mailing verification reports |

Frontend — `frontend/.env.local`: `NEXT_PUBLIC_API_BASE`, the browser-visible backend origin.

### PostgreSQL

The schema is portable; SQLite is the default only so the stack runs with no setup.

```bash
createdb qrwatermark
# then in backend/.env:
DATABASE_URL=postgresql+psycopg2://USER:PASSWORD@localhost:5432/qrwatermark
```

Re-run `make seed`. Tables are created on startup; Alembic is installed if you prefer managed
migrations.

### Optional: pyzbar

QR decoding uses OpenCV's detector. `pyzbar` is used as a second decoder when the native
library is present (`brew install zbar`) — everything works without it.

---

## Tests

```bash
make test
```

**42 backend tests.** The crypto suite covers the Merkle tree (inclusion proofs across tree
shapes, domain separation, order sensitivity, single-leaf change) and the watermark (round
trip, wrong key, semi-fragile under Gaussian noise, destroyed by overwrite). The integration
suite drives the real HTTP API: issuance, authentic verification, optical QR recovery from the
printed stamp, a text edit **localised to the exact cell**, redaction with no text change,
footer stripping, page removal, unprotected files, revocation and reinstatement, role
enforcement, dashboards and the audit trail.

The frontend is checked with `tsc --noEmit`, ESLint and a production `next build`.

---

## Honest limits

- Localisation is to a grid cell, not a word. The grid is configurable.
- Raster digests are reproducible because issuance and verification render with the same
  library version. After a renderer upgrade they would need recomputing; text digests are
  unaffected. `ENABLE_RASTER_HASH=false` removes the coupling, at the cost of missing
  image-only edits.
- Print-and-rescan is out of scope — that channel destroys both the raster digest and the DWT
  payload. Verification operates on the digital file.
- Text at or below 3pt is treated as marker ink and excluded from text hashing; it is still
  covered by the raster digest.
- The embedded-manifest fallback proves internal consistency, not that the authority issued the
  document. Reports label which baseline was used.
- ECDSA is the default because a 2048-bit RSA signature pushes the QR to 105 modules
  (0.18 mm each at the stamped size), which no phone camera can read. RSA-PSS is implemented
  and tested, and selectable.
