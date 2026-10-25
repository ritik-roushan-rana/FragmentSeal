# QR-Linked Fragmented Watermarking for Tamper-Evident Document Authentication

A document is watermarked so that every 32×32 pixel fragment carries a
cryptographic authenticator **for a different fragment**, and a QR code printed
on the page anchors the whole set to one signed commitment. Edit anything and
the system does not merely say "this changed" — it says *where*.

```
┌─ embed ─────────────────────────────────────────────────────────────────┐
│  page ──► fragments ──► digest each ──► HMAC tag each ──► Merkle root   │
│                                              │                  │       │
│                              key-driven dispersal π             │       │
│                                              ▼                  ▼       │
│                                tag(i) hidden in fragment π(i)   QR code │
└─────────────────────────────────────────────────────────────────────────┘
```

## Why the pieces are there

**Fragmented, not local.** Storing a fragment's authenticator inside itself
makes forgery a local problem: edit the region, recompute its tag, write it
back. Dispersing tag *i* into fragment *π(i)* — under a key-driven derangement —
means repairing one edit corrupts another fragment, whose tag lives somewhere
else again. Local forgery cascades into a document-wide one, which the secret
key makes infeasible.

**Position-bound tags.** Each tag is `HMAC(key, doc_id ‖ index ‖ digest)`.
Copying a block from elsewhere on the same page carries an authenticator
computed for the wrong index, so cut-and-paste is caught even though the pixels
are genuine.

**QR as the anchor, not the payload.** The QR holds a Merkle root over all
tags plus an Ed25519 signature — about 130 bytes. It never holds the tags and
never holds a key. A verifier reads it before touching a pixel, so replacing
the whole page with a differently-watermarked one is caught by the root even
though every fragment is internally consistent.

**The issuer's public key is deliberately absent from the QR.** A key carried
by the document it signs attests to nothing: a forger re-signs with their own
key and presents that. The verifier supplies the key it expects, so the
question becomes *"is this from the issuer I trust"* — the one worth asking.

## Install

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Use

```bash
.venv/bin/python -m qlfw keygen --out issuer.key
```

```bash
.venv/bin/python -m qlfw embed samples/certificate.png out/certificate.wm.png --keyfile issuer.key --note "NGU-2022-04417"
```

```bash
.venv/bin/python -m qlfw verify out/certificate.wm.png --keyfile issuer.key --map out/tampermap.png
```

`verify` exits 0 only for `AUTHENTIC`, so it drops straight into a pipeline.
Add `--json` for a machine-readable report naming the tampered fragments.

## The demo website

The easiest way to show the scheme to someone:

```bash
./web.sh
```

It opens `http://127.0.0.1:5005` with three steps — **Protect** a document,
**Forge** it, **Verify** it. The verdict appears as a green or red badge with
the tamper map rendered underneath.

The forgery step is deliberately not rigged: either the computer picks the
region at random, or you click the spot on the protected image and it forges
exactly there. Verification receives only the file and the key either way.
Everything runs on localhost; the issuer key is generated on first run into
`webapp/workspace/`.

## Demonstrating it from the terminal

`./present.sh` walks through the whole argument in seven steps, pausing between
each. It takes any document you give it, so the audience can supply their own:

```bash
./present.sh ~/their-document.pdf
```

Nothing about the attack is fixed. Step 6 hands the watermarked file back and
invites the audience to edit it in any tool they like; if they decline, a
target is chosen **at random at run time** instead. The verifier is never told
what changed, where, or that anything did — it receives only the file and the
key. `--rect random` is available on `tamper` directly, with `--seed` when you
need a run to be reproducible.

`./demo.sh` is the same story without the pauses, for a quick check.

Simulate an attack to see localization work:

```bash
.venv/bin/python -m qlfw tamper out/certificate.wm.png out/forged.png --mode text --rect 325,492,230,34 --text "9.94 / 10.00"
```

```bash
.venv/bin/python -m qlfw verify out/forged.png --keyfile issuer.key --map out/tampermap.png --grid
```

```
TAMPERED  localised edits detected
  merkle anchor : does NOT match QR
  issuer signature: valid
  fragments     : 15/1280 tampered (1.2%) [........................]
  guardian fallout: 15 fragment(s) flagged by dispersal, not themselves edited
  worst fragment: row 15, col 10 (27/36 bit errors)
```

The map tints the located edit **red** and guardian fallout **amber**. Other
commands: `inspect` (decode a QR manifest without the secret key), and
`--carrier lsb` for the fragile variant.

PDFs work the same way; pages are rasterised, watermarked, and written back as
a lossless multi-page PDF, one manifest and QR per page.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `AUTHENTIC` | Root matches, every fragment checks out, signature from the expected issuer. |
| `TAMPERED` | Some fragments fail. The map says which. |
| `UNTRUSTED_ANCHOR` | The anchor is not signed by the expected issuer — a forged QR, or the wrong key file. The report says which is likelier. |
| `WRONG_KEY_OR_REPLACED` | Every fragment fails — wrong key, or a different document. |
| `UNVERIFIABLE` | Geometry no longer matches; fragment alignment is lost. |

`signature_ok` is three-valued. `None` means the question was never asked —
unsigned document, or no issuer key supplied — and is never reported as a pass.

## Carriers

| | `dct` (default) | `lsb` |
| --- | --- | --- |
| Domain | Mid-band DCT, QIM | Bit 0 of the last channel |
| Fragility | Semi-fragile | Fragile |
| Survives | JPEG down to q92; additive noise to σ≈1 | Nothing; any re-encode fails |
| Colour | Converts to grayscale | Authenticates all channels |
| PSNR | ≈29 dB | ≈63 dB |
| Use for | Scanned or re-encoded documents | Born-digital documents never re-encoded |

## Two problems worth knowing about

**The scheme has to close on itself.** A fragment's tag depends on its content,
but that content is where some *other* fragment's tag is written. The split is
made explicit: the digest reads only DC and the lowest AC coefficients, the
payload only mid-band ones, and the digest coefficients are snapped onto a
quantisation lattice at embed time so the uint8 round-trip cannot move them
into a neighbouring bucket. `embed` then iterates to a genuine fixed point and
reads the digests back from the *rendered* image — the document that ships is
one that has been verified against itself, not one assumed consistent. If it
cannot converge, it refuses to write a file.

**A document page is almost all saturated white.** A saturated block has no
room to be modulated: the clip back to `uint8` simply erases the payload. The
first working version lost 11% of its payload bits this way. The tonal range
is therefore compressed by one QIM step at each end before embedding, which is
what buys the headroom back — and what costs the `dct` carrier its PSNR,
since the background sits a shade off pure white. That shift, not the
watermark, is most of the 29 dB.

## Limits

* **The `dct` carrier's robustness is narrow, and JPEG tolerance does not
  imply noise tolerance.** At the default `--strength 8` it is clean through
  JPEG q92 but only to additive Gaussian noise of σ≈1; by σ=1.5 most of the
  page is flagged. `--strength 16` moves those to q90 and σ≈2 at the cost of
  PSNR (29 dB → 24 dB). Past either limit it fails loudly
  (`WRONG_KEY_OR_REPLACED`) rather than producing a plausible-looking partial
  tamper map — but a page flagged end to end means "could not verify", not
  "forged everywhere".
* **PDF density must be 72·2^k** (72/144/288/576 DPI). At any other value the
  page box is a fractional number of points, pdfium's raster comes back a pixel
  off, and the resampling destroys the watermark. Other values are snapped.
* **Localization trades precision for recall.** When a fragment fails it may be
  innocent — its guardian was the thing edited. The refinement keeps only
  fragments whose guardian relationship is consistent with them being the
  edited one, which strips most of that halo but cannot strip all of it:
  if an edited fragment's own guardian was *also* inside the edit, a third
  fragment is promoted. Measured over 400 random keys on a 4-fragment edit,
  the edit was never missed, strays averaged 0.2 and never exceeded 2. Red is
  high-precision, amber is "look here too"; neither is exact.
* **Verification needs the secret key.** The Ed25519 signature gives public
  *attribution* of the anchor; authenticating the pixels needs the HMAC key.
  True public verifiability would need a different construction.
* **Geometric attacks are out of scope.** Rotation, cropping and rescaling
  destroy fragment alignment; those report `UNVERIFIABLE`, not `AUTHENTIC`.
* **Print-and-scan is not supported.** The `dct` carrier tolerates mild
  recompression, not a trip through a printer and a scanner.

## Layout

```
qlfw/
  config.py     scheme parameters, carried in the QR
  crypto.py     HMAC tags, the dispersal derangement, Merkle root, Ed25519
  transform.py  vectorised 8×8 DCT and fragment tiling
  carriers.py   DCT-QIM and LSB carriers; the digest/payload split lives here
  manifest.py   the packed binary QR record, and the self-validating renderer
  pipeline.py   embed (fixed-point) and verify (localisation)
  docio.py      images, PDF rasterisation, QR attachment
  pdfwrite.py   lossless image-per-page PDF writer
  report.py     tamper-map overlay and console output
  tamper.py     attack simulation, for demos and tests
  cli.py        the command line
tests/          59 tests: crypto, manifest/QR, pipeline, CLI, PDF round-trip
```

## Tests

```bash
.venv/bin/python -m pytest tests -q
```

The suite pins the claims this README makes, including the JPEG breakdown
point and the PDF raster round-trip being bit-exact — both are places where a
regression would quietly produce false verdicts rather than fail loudly.
