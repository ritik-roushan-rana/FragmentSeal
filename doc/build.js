const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, TabStopType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, PageBreak,
  ImageRun, Footer, PageNumber, TableOfContents, LevelFormat, convertInchesToTwip,
} = require("docx");

const BODY = "Calibri", MONO = "Consolas";
// Everything prints black. Shading and rules carry the structure instead of
// colour, so the document survives a monochrome printer unchanged.
const INK = "000000", RULE = "000000", HEAD_FILL = "D9D9D9", ZEBRA = "F2F2F2";
// A4 is 11906 DXA wide; with 1420 DXA side margins the text area is 9066.
// Tables are normalised to exactly this, or they overhang the right margin.
const CW = 9066;

// ---------- helpers ----------
const p = (text, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, before: o.before ?? 0, line: o.line ?? 276 },
  alignment: o.align ?? AlignmentType.JUSTIFIED, indent: o.indent, numbering: o.numbering,
  children: [new TextRun({ text, font: o.font ?? BODY, size: o.size ?? 22,
    bold: o.bold, italics: o.italics, color: o.color ?? INK })],
});

// A paragraph built from alternating plain / bold-or-mono spans.
const rich = (spans, o = {}) => new Paragraph({
  spacing: { after: o.after ?? 120, line: 276 },
  alignment: o.align ?? AlignmentType.JUSTIFIED, indent: o.indent, numbering: o.numbering,
  children: spans.map(s => typeof s === "string"
    ? new TextRun({ text: s, font: BODY, size: 22, color: INK })
    : new TextRun({ text: s.t, font: s.code ? MONO : BODY,
                   size: s.code ? 19 : 22, bold: s.b, italics: s.i, color: INK })),
});

const h1 = (text, newPage = false) => new Paragraph({
  heading: HeadingLevel.HEADING_1, pageBreakBefore: newPage,
  spacing: { before: newPage ? 0 : 360, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
  children: [new TextRun({ text, font: BODY, size: 28, bold: true, color: INK })],
});
const h1Plain = (text, newPage = false) => new Paragraph({
  pageBreakBefore: newPage, spacing: { before: newPage ? 0 : 360, after: 160 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
  children: [new TextRun({ text, font: BODY, size: 28, bold: true, color: INK })],
});
const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 120 },
  children: [new TextRun({ text, font: BODY, size: 24, bold: true, color: INK })],
});
const h3 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 },
  children: [new TextRun({ text, font: BODY, size: 22, bold: true, color: INK })],
});

const bullet = (text) => p(text, { numbering: { reference: "dots", level: 0 }, after: 80 });
const bulletRich = (spans) => rich(spans, { numbering: { reference: "dots", level: 0 }, after: 80 });
const numbered = (text) => p(text, { numbering: { reference: "steps", level: 0 }, after: 80 });
const numberedRich = (spans) => rich(spans, { numbering: { reference: "steps", level: 0 }, after: 80 });

const code = (lines) => new Paragraph({
  spacing: { before: 100, after: 160, line: 240 },
  shading: { type: ShadingType.CLEAR, fill: ZEBRA },
  indent: { left: 220, right: 220 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: INK, space: 8 } },
  children: lines.flatMap((l, i) => [
    ...(i ? [new TextRun({ break: 1 })] : []),
    new TextRun({ text: l, font: MONO, size: 18, color: INK }),
  ]),
});

const caption = (text) => p(text, {
  align: AlignmentType.CENTER, size: 18, italics: true, color: INK, after: 240,
});

function table(headers, rows, rawWidths) {
  // Scale the requested proportions to the real text width, exactly.
  const total = rawWidths.reduce((a, b) => a + b, 0);
  const widths = rawWidths.map(w => Math.round(w * CW / total));
  widths[widths.length - 1] += CW - widths.reduce((a, b) => a + b, 0);
  const cell = (text, { head = false, zebra = false, bold = false } = {}, w) =>
    new TableCell({
      width: { size: w, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: head ? HEAD_FILL : (zebra ? ZEBRA : "FFFFFF") },
      margins: { top: 70, bottom: 70, left: 110, right: 110 },
      children: [new Paragraph({
        spacing: { after: 0, line: 240 },
        children: [new TextRun({ text, font: BODY, size: 19,
          bold: head || bold, color: INK })],
      })],
    });
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: ["top", "bottom", "left", "right", "insideHorizontal", "insideVertical"]
      .reduce((o, k) => (o[k] = { style: BorderStyle.SINGLE, size: 4, color: INK }, o), {}),
    rows: [
      new TableRow({ tableHeader: true,
        children: headers.map((t, i) => cell(t, { head: true }, widths[i])) }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((t, i) => cell(String(t), { zebra: ri % 2 === 1, bold: i === 0 }, widths[i])),
      })),
    ],
  });
}

const figure = (file, widthPx, heightPx) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 160, after: 60 },
  children: [new ImageRun({ type: "png", data: fs.readFileSync(file),
    transformation: { width: widthPx, height: heightPx } })],
});

const spacer = (n = 1) => Array.from({ length: n }, () => p("", { after: 0 }));

// ---------- title page ----------
const titlePage = [
  ...spacer(4),
  p("QR-Linked Fragmented Watermarking", {
    align: AlignmentType.CENTER, size: 40, bold: true, color: INK, after: 80 }),
  p("for Tamper-Evident Document Authentication", {
    align: AlignmentType.CENTER, size: 30, bold: true, color: INK, after: 300 }),
  new Paragraph({
    alignment: AlignmentType.CENTER, spacing: { after: 280 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: INK, space: 10 } },
    children: [new TextRun({ text: "Project Report", font: BODY, size: 24,
      color: INK, allCaps: true, characterSpacing: 60 })],
  }),
  p("A content-fragile watermarking scheme that detects document tampering and "
    + "localises it to the altered region, anchored to a signed QR commitment.",
    { align: AlignmentType.CENTER, size: 22, italics: true, color: INK, after: 560 }),
  ...spacer(6),
  p("Submitted by", { align: AlignmentType.CENTER, size: 20, color: INK, after: 60 }),
  p("Ritik Rana", { align: AlignmentType.CENTER, size: 26, bold: true, after: 400 }),
  p("October 2026", { align: AlignmentType.CENTER, size: 20, color: INK, after: 0 }),
];

// ---------- abstract + TOC ----------
const front = [
  h1("Abstract", true),
  p("A digital signature on a document answers one question: has this file changed? "
    + "It cannot say which part changed, and it does not survive the document being "
    + "rendered, printed or re-encoded. This project presents QLFW, a watermarking "
    + "scheme that embeds authentication data into the pixels themselves so that "
    + "tampering is both detected and located."),
  p("The page is partitioned into 32x32 pixel fragments. Each fragment's visual "
    + "content is reduced to a digest, and that digest is converted into a 64-bit "
    + "keyed authentication tag bound to the fragment's position. The tag is then "
    + "hidden not in its own fragment but in a different one, chosen by a key-driven "
    + "derangement, so that the document is interlocked globally rather than being a "
    + "collection of independently valid blocks. A Merkle root over all tags is signed "
    + "with Ed25519 and printed on the page as a QR code, which binds the sheet to one "
    + "exact set of authenticators and to one issuer."),
  p("The implementation provides two carriers: a semi-fragile DCT quantisation-index-"
    + "modulation carrier that tolerates mild recompression, and a fragile LSB carrier "
    + "for born-digital documents. On a 1024x1280 certificate the DCT carrier produces "
    + "1280 fragments at 29.26 dB PSNR. Across 400 trials with independent keys, a "
    + "four-fragment edit was never missed, and false positives averaged 0.2 fragments "
    + "and never exceeded 2. The system is implemented in 1,707 lines of Python with a "
    + "command-line interface and a suite of 61 tests."),
  p("Keywords: fragile watermarking, tamper localisation, document authentication, "
    + "discrete cosine transform, quantisation index modulation, Merkle tree, Ed25519.",
    { size: 20, italics: true, before: 160 }),

  h1Plain("Table of Contents"),
  p("If the list below is empty, select it and press F9 (Word) or right-click and "
    + "choose Update Field.", { size: 19, italics: true, color: INK }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
];

// ---------- body ----------
const body = [
  h1("1. Introduction", true),
  p("Documents that carry consequence — academic transcripts, contracts, medical "
    + "records, land titles — circulate as images and PDFs. Any of them can be opened "
    + "in an ordinary image editor and altered in seconds. The alteration leaves no "
    + "trace that an unaided reader can see."),
  p("The conventional defence is a detached cryptographic signature. It is effective "
    + "while the document stays in its original binary form, and useless afterwards. "
    + "Rendering a signed PDF to an image, printing it, or re-encoding it all discard "
    + "the signature while preserving everything a human reads. A signature is also "
    + "binary in its verdict: it reports that the file differs from what was signed, "
    + "but cannot indicate where, which matters when the question is whether a single "
    + "figure was altered or the whole document is counterfeit."),
  p("Watermarking takes the opposite approach. Authentication data is carried inside "
    + "the pixels, so it travels with the visual content rather than with the file "
    + "format. This project builds such a scheme and addresses the two properties that "
    + "make one useful in practice: it must say where the document was altered, and it "
    + "must resist a forger who holds the watermarked document and wishes to repair it."),

  h1("2. Problem Statement"),
  p("Design and implement a document authentication system that satisfies all of the "
    + "following simultaneously:"),
  bulletRich([{ t: "Tamper detection. ", b: true },
    "Any modification to the document's visual content must be detected."]),
  bulletRich([{ t: "Tamper localisation. ", b: true },
    "The system must identify which regions were altered, not merely that an "
    + "alteration occurred."]),
  bulletRich([{ t: "Resistance to repair. ", b: true },
    "An adversary holding the watermarked document, but not the secret key, must be "
    + "unable to edit a region and restore consistency."]),
  bulletRich([{ t: "Resistance to splicing. ", b: true },
    "Genuine content copied from one position to another within the same document "
    + "must be rejected."]),
  bulletRich([{ t: "Origin binding. ", b: true },
    "Re-watermarking an altered document with the adversary's own key must not yield "
    + "a document that verifies as the issuer's."]),
  bulletRich([{ t: "Imperceptibility. ", b: true },
    "The watermark must not interfere with reading the document."]),
  p("The central technical obstacle is circularity. A fragment's authentication tag "
    + "is computed from that fragment's content, yet the tag must be stored in the "
    + "pixels — which changes the content it was computed from. Any workable scheme "
    + "must break this dependency rather than assume it away.", { before: 100 }),

  h1("3. Objectives"),
  numbered("To design a fragment-level authentication scheme in which a fragment's "
    + "authenticator is stored outside that fragment, so that local forgery propagates "
    + "into a document-wide inconsistency."),
  numbered("To separate, in the frequency domain, the coefficients that determine a "
    + "fragment's digest from those that carry its payload, thereby eliminating the "
    + "circular dependency between content and tag."),
  numbered("To bind the document to a compact, signed public commitment carried as a "
    + "QR code, giving origin attribution independent of the pixel-level watermark."),
  numbered("To implement both a semi-fragile and a fragile carrier, and to characterise "
    + "empirically where each one ceases to work."),
  numbered("To deliver a working command-line tool operating on both images and PDFs, "
    + "with an automated test suite."),

  h1("4. Background and Related Approaches"),
  h2("4.1 Detached digital signatures"),
  p("A signature over the file's bytes gives strong integrity and origin guarantees, "
    + "but is bound to the container rather than the content. It does not survive "
    + "format conversion and provides no localisation."),
  h2("4.2 Fragile watermarking"),
  p("Classical fragile schemes embed a checksum of each block into the least "
    + "significant bits of that same block. These detect any change and localise it "
    + "well, but store each block's evidence inside the block it protects, which leaves "
    + "the document a collection of independently valid units vulnerable to collage "
    + "attacks, in which an adversary assembles a new document from authenticated "
    + "blocks taken from genuine ones."),
  h2("4.3 Semi-fragile watermarking"),
  p("Semi-fragile schemes embed in transform coefficients so the watermark tolerates "
    + "benign processing such as mild recompression while still failing on genuine "
    + "edits. The difficulty is calibration: the margin that absorbs compression noise "
    + "is the same margin an attacker can hide a small edit within."),
  h2("4.4 Position of this work"),
  p("QLFW combines a keyed, position-bound tag per fragment (defeating splicing), a "
    + "key-driven dispersal of tags across fragments (defeating local repair and "
    + "collage), and a signed Merkle anchor carried in a QR code (defeating wholesale "
    + "re-watermarking). The contribution is the composition and a working, measured "
    + "implementation rather than any single primitive."),

  h1("5. System Architecture", true),
  p("The system has two operations, embedding and verification, over six components."),
  figure("doc/figs/fig_arch.png", 560, 280),
  caption("Figure 1 — Embedding pipeline. Tags are dispersed across fragments; only "
    + "their Merkle root reaches the QR code."),
  h2("5.1 Components"),
  table(
    ["Module", "Responsibility"],
    [
      ["transform.py", "Vectorised 8x8 DCT and fragment tiling"],
      ["carriers.py", "DCT-QIM and LSB carriers; the digest / payload coefficient split"],
      ["crypto.py", "HMAC tags, dispersal derangement, Merkle root, Ed25519 signing"],
      ["manifest.py", "Packed binary QR record and the self-validating QR renderer"],
      ["pipeline.py", "Embedding fixed-point search; verification and localisation"],
      ["docio.py / pdfwrite.py", "Image and PDF input, lossless PDF output, QR attachment"],
    ], [2600, 6760]),
  caption("Table 1 — Principal modules and their responsibilities."),

  h2("5.2 Data flow"),
  numberedRich([{ t: "Partition. ", b: true },
    "The page is padded by edge replication to a multiple of the fragment size and "
    + "divided into N fragments. Padding rather than cropping ensures no original "
    + "pixel falls outside an authenticated fragment."]),
  numberedRich([{ t: "Digest. ", b: true },
    "Each fragment is reduced to a digest over quantised low-frequency DCT "
    + "coefficients, describing its coarse appearance."]),
  numberedRich([{ t: "Tag. ", b: true },
    "Each digest becomes a 64-bit keyed tag bound to the fragment index and document "
    + "identifier."]),
  numberedRich([{ t: "Disperse. ", b: true },
    "A key-driven derangement assigns the tag of fragment i to fragment pi(i)."]),
  numberedRich([{ t: "Embed. ", b: true },
    "Tags are written into mid-band DCT coefficients by quantisation index modulation."]),
  numberedRich([{ t: "Anchor. ", b: true },
    "A Merkle root over all tags is signed and rendered as a QR code placed outside "
    + "the authenticated region."]),

  h1("6. Methodology", true),

  h2("6.1 Fragmentation"),
  p("The page is divided into non-overlapping square fragments, 32 pixels on a side by "
    + "default. The size is a direct trade-off: smaller fragments localise more "
    + "precisely but offer less capacity for a payload, while larger fragments carry "
    + "more bits but blur the location of an edit. At 32 pixels a fragment spans 16 "
    + "DCT sub-blocks, and the resulting capacity of 64 bits matches the tag length "
    + "exactly. A 1024x1280 page yields 1280 fragments."),

  h2("6.2 Separating digest from payload"),
  p("The circularity identified in Section 2 is resolved by partitioning each 8x8 DCT "
    + "sub-block's coefficients into two disjoint sets:"),
  bulletRich([{ t: "Digest coefficients ", b: true },
    "— the DC term and four lowest AC terms, at positions (0,0), (0,1), (1,0), (0,2) "
    + "and (2,0). These describe the fragment's coarse appearance. They are never "
    + "modified by embedding."]),
  bulletRich([{ t: "Payload coefficients ", b: true },
    "— four mid-band terms at (1,2), (2,1), (2,2) and (1,3). These carry tag bits. "
    + "They are low enough in frequency to survive mild recompression, high enough to "
    + "remain invisible."]),
  p("Because the sets are disjoint, writing a payload cannot alter any digest. One "
    + "residual coupling remains: the inverse transform and rounding back to 8-bit "
    + "integers perturbs every coefficient slightly. This is removed by snapping each "
    + "digest coefficient onto a quantisation lattice of step 16 during embedding, so "
    + "that the measured round-trip drift — at most 1.21 against a tolerance of 8 — "
    + "cannot move a coefficient into a neighbouring bucket."),

  h2("6.3 Tag generation"),
  p("Each fragment's authenticator is a truncated HMAC-SHA256:"),
  code(["tag(i) = HMAC(K_tag, doc_id || i || digest(i))   truncated to 64 bits"]),
  p("Three inputs each serve a purpose. The digest binds the tag to the fragment's "
    + "content. The index i binds it to a position, so genuine content copied "
    + "elsewhere on the page carries an authenticator computed for the wrong location "
    + "and is rejected. The document identifier binds it to one document, preventing "
    + "fragments from being transplanted between documents issued under the same key."),

  h2("6.4 Dispersal"),
  p("The tag for fragment i is embedded into fragment pi(i), where pi is a derangement "
    + "— a permutation with no fixed points — derived deterministically from the secret "
    + "key and the document identifier by a keystream-driven Fisher-Yates shuffle."),
  p("This is the scheme's central structural decision. Were a tag stored in the "
    + "fragment it authenticates, every fragment would be a self-contained verifiable "
    + "unit and the document a bag of interchangeable parts. Under dispersal, altering "
    + "fragment i is detected through fragment pi(i); repairing that evidence would "
    + "require modifying pi(i), which invalidates the tag stored in pi(pi(i)), and so "
    + "on. A local edit therefore propagates into a document-wide inconsistency that "
    + "cannot be resolved without the key."),

  h2("6.5 The QR anchor"),
  p("All N tags are combined into a single 32-byte Merkle root with domain-separated "
    + "leaf and node prefixes. The root, the scheme parameters, the document "
    + "identifier and an issue timestamp form a 69-byte record, signed with Ed25519 "
    + "and encoded as base32 — whose alphabet lies within QR alphanumeric mode, "
    + "packing 5.5 bits per character against byte mode's 8."),
  p("The issuer's public key is deliberately excluded from the record. A key carried "
    + "by the document it signs attests to nothing, since a forger re-signs with their "
    + "own key and presents that. The verifier supplies the key it expects, so the "
    + "question asked becomes whether the document originates from a specific trusted "
    + "issuer."),
  p("The QR is placed on a strip below the document, outside the authenticated region, "
    + "because overlaying it would overwrite watermarked pixels. A verifier recovers "
    + "the authenticated region by cropping to the dimensions stated in the manifest."),

  h2("6.6 Embedding as a fixed-point search"),
  p("Although the coefficient split makes digests independent of the payload in "
    + "principle, the implementation does not rely on that assumption. Embedding "
    + "iterates: a candidate payload is rendered to an 8-bit image, digests are read "
    + "back from that rendered image, tags are recomputed and dispersed, and the result "
    + "is compared with the payload that produced it. The process terminates only when "
    + "the two agree, at which point the document is demonstrably self-consistent. If "
    + "no fixed point is reached within eight rounds, the tool refuses to write output "
    + "rather than ship a document that would fail its own verification. In practice "
    + "convergence occurs in two rounds."),

  h2("6.7 Handling saturation"),
  p("A document page is predominantly saturated white with black text. A saturated "
    + "block has no headroom to be modulated: the clip back to the 8-bit range erases "
    + "the payload. In the initial implementation this cost 11 percent of all payload "
    + "bits, concentrated in the background. The tonal range is therefore compressed by "
    + "one quantisation step at each end before embedding, which restores the headroom. "
    + "This compression, rather than the watermark itself, accounts for most of the "
    + "DCT carrier's distortion."),

  h2("6.8 Verification and localisation"),
  p("Verification receives only the document and the key. For each fragment it "
    + "recomputes the digest from the current pixels, recomputes the expected tag, and "
    + "compares it against the tag extracted from fragment pi(i). A Hamming distance "
    + "above the tolerance marks a mismatch."),
  p("A mismatched fragment is not necessarily an altered one: it also fails when the "
    + "guardian holding its tag was the region edited. The reported tamper set is "
    + "therefore refined to those fragments whose own guardian relationship is "
    + "consistent with them being the edited party, which removes most of this halo. "
    + "The remainder is reported separately as guardian fallout."),

  h1("7. Implementation", true),
  h2("7.1 Technology"),
  p("Python 3.14, with NumPy for vectorised transforms, Pillow for image handling, "
    + "the cryptography library for Ed25519, OpenCV for QR detection, qrcode for QR "
    + "generation, and pypdfium2 for PDF rasterisation. The 8x8 DCT is implemented "
    + "directly as a matrix product applied to the whole image at once, which avoids "
    + "per-block iteration."),
  h2("7.2 Carriers"),
  table(
    ["Property", "DCT carrier (default)", "LSB carrier"],
    [
      ["Domain", "Mid-band DCT, QIM", "Bit 0 of the last channel"],
      ["Fragility", "Semi-fragile", "Fragile"],
      ["JPEG tolerance", "Clean to quality 92", "None; any re-encode fails"],
      ["Noise tolerance", "Sigma approx. 1", "None"],
      ["Colour", "Converts to grayscale", "Authenticates all channels"],
      ["PSNR", "29.26 dB", "63.21 dB"],
      ["Intended use", "Scanned or re-encoded documents", "Born-digital documents"],
    ], [2200, 3880, 3280]),
  caption("Table 2 — Comparison of the two embedding carriers."),

  h2("7.3 Lossless output"),
  p("Two output paths were found to destroy the watermark silently and required "
    + "replacement. Pillow encodes PDF pages with DCTDecode, that is JPEG, so a custom "
    + "FlateDecode PDF writer was implemented. Separately, PDF rasterisation returns a "
    + "page one pixel off at densities where the page box is a fractional number of "
    + "points; rendering density is therefore restricted to 72 x 2^k DPI, where the "
    + "round-trip is bit-exact."),

  h2("7.4 Command-line interface"),
  table(
    ["Command", "Function"],
    [
      ["keygen", "Create an issuer key file (HMAC key plus Ed25519 pair, mode 0600)"],
      ["embed", "Watermark a document and emit its QR anchor"],
      ["verify", "Authenticate a document, localise tampering, write a tamper map"],
      ["inspect", "Decode and print a QR manifest without the secret key"],
      ["tamper", "Simulate an attack, for demonstration and testing"],
    ], [2000, 7360]),
  caption("Table 3 — Command-line operations."),
  p("Verification exits with status 0 only for an authentic document, allowing the "
    + "tool to be used directly in automated pipelines. A machine-readable report "
    + "naming the tampered fragments is available via a JSON output flag."),

  h1("8. Results", true),
  h2("8.1 Imperceptibility and convergence"),
  p("On the 1000x1280 test certificate, padded to 1024x1280 and divided into 1280 "
    + "fragments, the DCT carrier achieves 29.26 dB PSNR and the LSB carrier 63.21 dB. "
    + "Both reach a self-consistent fixed point in two rounds. Figure 2 shows the "
    + "watermarked document; the text remains fully legible."),
  figure("doc/figs/fig_watermarked.png", 230, 352),
  caption("Figure 2 — Watermarked certificate with its QR anchor on the strip below."),

  h2("8.2 Tamper localisation"),
  p("The value 9.14 was altered to 9.94 using an ordinary text overlay. Verification, "
    + "given only the file and the key, reported 13 tampered fragments beginning at "
    + "row 15, column 10 — precisely the altered region, which begins at pixel "
    + "coordinates (325, 492) and therefore at fragment (15, 10)."),
  figure("doc/figs/fig_detail.png", 470, 196),
  caption("Figure 3 — Detail before (top) and after (bottom) verification. Red marks "
    + "the located edit; amber marks guardian fallout."),
  figure("doc/figs/fig_tampermap.png", 230, 288),
  caption("Figure 4 — Full-page tamper map. The scattered amber fragments are those "
    + "whose authenticators were stored inside the edited region."),

  h2("8.3 Localisation accuracy"),
  p("A four-fragment edit was applied under 400 independently generated keys, 200 per "
    + "carrier, and the reported tamper set compared against ground truth."),
  table(
    ["Carrier", "Trials", "Edit missed", "Mean false positives", "Max false positives"],
    [
      ["DCT", "200", "0", "0.20", "2"],
      ["LSB", "200", "0", "0.14", "2"],
    ], [1700, 1500, 1900, 2380, 1880]),
  caption("Table 4 — Localisation accuracy over 400 trials with independent keys."),
  p("Recall is complete: the edit was never missed. False positives arise from the "
    + "dispersal itself — when an edited fragment's guardian was also inside the edit, "
    + "a third fragment is promoted — and are bounded at two.", { before: 60 }),

  h2("8.4 Robustness"),
  p("The DCT carrier was subjected to JPEG recompression and additive Gaussian noise "
    + "at two strength settings."),
  table(
    ["Attack", "Strength 8 (default)", "Strength 16"],
    [
      ["JPEG quality 95", "Clean", "Clean"],
      ["JPEG quality 92", "Clean", "Clean"],
      ["JPEG quality 90", "2 of 1280 flagged", "Clean"],
      ["JPEG quality 85", "Total failure", "—"],
      ["Gaussian noise, sigma 0.75", "Clean", "Clean"],
      ["Gaussian noise, sigma 1.0", "2 of 1280 flagged", "3 of 1280 flagged"],
      ["Gaussian noise, sigma 1.5", "1043 of 1280 flagged", "—"],
      ["Gaussian noise, sigma 2.0", "Total failure", "146 of 1280 flagged"],
      ["PSNR", "29.26 dB", "23.66 dB"],
    ], [3200, 3080, 3080]),
  caption("Table 5 — Robustness of the DCT carrier, and the cost of raising embedding "
    + "strength."),
  p("Two observations follow. First, tolerance to JPEG does not imply tolerance to "
    + "additive noise: the carrier is clean through JPEG quality 92 but fails by noise "
    + "of sigma 1.5. Second, raising the embedding strength buys robustness at a "
    + "measurable cost in fidelity, and the trade-off is exposed as a parameter rather "
    + "than fixed. Beyond either limit the system fails loudly rather than producing a "
    + "plausible but wrong tamper map.", { before: 60 }),

  h2("8.5 QR anchor reliability"),
  p("OpenCV's QR decoder proved unreliable on dense symbols, failing roughly 8 percent "
    + "of reads even on undamaged images, with failures occurring in decoding rather "
    + "than detection. Two measures were taken. The manifest was compacted from a JSON "
    + "representation of 428 characters to a packed binary record of 218, encoded in "
    + "base32 to exploit QR alphanumeric mode. Second, the rendered QR is decoded from "
    + "the composed page before the document is written, stepping through error-"
    + "correction levels until one round-trips."),
  table(
    ["Configuration", "Failures"],
    [
      ["JSON manifest, single decode attempt", "10 of 40"],
      ["Packed binary manifest, multi-view decode", "3 of 80"],
      ["Packed binary, validated on the composed page", "0 of 80"],
    ], [6000, 3360]),
  caption("Table 6 — QR anchor read reliability at each stage of refinement."),

  h2("8.6 Testing"),
  p("The implementation is covered by 61 automated tests across 559 lines, spanning "
    + "the cryptographic primitives, the manifest wire format, both carriers, the PDF "
    + "round-trip and the command-line interface. Several encode claims made in this "
    + "report, including the JPEG breakdown point, the bit-exactness of the PDF raster "
    + "round-trip and the bound on false positives, because a regression in any of "
    + "these would produce incorrect verdicts silently rather than failing visibly."),

  h1("9. Security Analysis", true),
  table(
    ["Attack", "Defence"],
    [
      ["Edit a region", "Digest changes; the tag stored in the guardian fragment no longer matches"],
      ["Repair the edited region", "Requires the key; repairing the guardian cascades to its own guardian"],
      ["Splice content within the page", "Tags are bound to the fragment index, so moved content carries the wrong tag"],
      ["Transplant between documents", "Tags are bound to the document identifier"],
      ["Re-watermark with the attacker's key", "The Merkle root in the signed QR no longer matches"],
      ["Forge the QR anchor", "Ed25519 signature over the whole record, verified against an expected issuer key"],
      ["Substitute the whole document", "Document identifier and Merkle root both bind the anchor to one page"],
    ], [3000, 6360]),
  caption("Table 7 — Attack surface and corresponding defences."),
  p("The security of fragment authentication rests on the secrecy of the HMAC key; "
    + "forging a single tag without it succeeds with probability 2^-64. The security of "
    + "origin attribution rests on Ed25519 and is independent of the HMAC key.",
    { before: 60 }),

  h1("10. Limitations"),
  bulletRich([{ t: "Verification requires the secret key. ", b: true },
    "The Ed25519 signature provides public attribution of the anchor, but "
    + "authenticating the pixels requires the HMAC key. Genuine public verifiability "
    + "would need a different construction."]),
  bulletRich([{ t: "Narrow robustness envelope. ", b: true },
    "The DCT carrier tolerates JPEG to quality 92 and noise to sigma 1 at default "
    + "settings. Beyond that it reports failure rather than a partial result."]),
  bulletRich([{ t: "Geometric attacks are out of scope. ", b: true },
    "Rotation, cropping and rescaling destroy fragment alignment; these are reported "
    + "as unverifiable rather than authentic."]),
  bulletRich([{ t: "Print and scan is not supported. ", b: true },
    "The carrier tolerates mild recompression, not a full analogue round trip."]),
  bulletRich([{ t: "Localisation is not exact. ", b: true },
    "Recall is complete but precision is bounded rather than perfect, with up to two "
    + "false positives observed."]),
  bulletRich([{ t: "Chroma is unprotected under the DCT carrier. ", b: true },
    "That carrier converts to grayscale so every authenticated byte lies in the plane "
    + "it controls; the LSB carrier authenticates all channels."]),

  h1("11. Future Work"),
  bullet("Geometric resynchronisation, using registration marks or a template, to "
    + "recover fragment alignment after rotation or cropping."),
  bullet("A print-and-scan robust carrier, which would require a substantially lower "
    + "embedding rate and explicit halftone modelling."),
  bullet("Self-embedding content recovery, in which each fragment additionally carries "
    + "a compressed thumbnail of another, allowing the original appearance of an "
    + "altered region to be approximately reconstructed."),
  bullet("Public verifiability without a shared secret, for example by committing to "
    + "per-fragment values in a structure that supports public proofs."),
  bullet("A graphical interface for non-technical operators in a registrar's office."),

  h1("12. Conclusion"),
  p("This project implements a document authentication scheme that detects tampering "
    + "and localises it to the altered region, resists repair by an adversary who lacks "
    + "the key, and binds each document to a signed public anchor carried as a QR code. "
    + "The circular dependency between a fragment's content and its authenticator — the "
    + "principal obstacle to any such scheme — is resolved by partitioning the DCT "
    + "coefficients into disjoint digest and payload sets, and the implementation "
    + "verifies self-consistency by fixed-point iteration rather than assuming it."),
  p("The measured results support the design. Localisation recall was complete across "
    + "400 trials with a false-positive bound of two fragments. Both carriers converge "
    + "in two rounds, and the semi-fragile carrier tolerates recompression to JPEG "
    + "quality 92 at 29.26 dB fidelity."),
  p("Equally informative were the failures encountered during development. Saturated "
    + "document backgrounds silently destroyed 11 percent of payload bits until tonal "
    + "headroom was introduced; two separate output paths were found to re-encode the "
    + "document lossily and had to be replaced; and the QR decoder failed on 8 percent "
    + "of dense symbols until the manifest was compacted and validated on the composed "
    + "page. Each was invisible in casual testing and would have produced confidently "
    + "incorrect verdicts in deployment. The system's stated limits are therefore "
    + "measured rather than assumed, and it is designed to fail audibly where it "
    + "fails at all."),

  h1("References"),
  p("[1] M. Wu and B. Liu, \"Watermarking for image authentication,\" Proceedings of "
    + "the IEEE International Conference on Image Processing, 1998.", { after: 80 }),
  p("[2] P. W. Wong and N. Memon, \"Secret and public key image watermarking schemes "
    + "for image authentication and ownership verification,\" IEEE Transactions on "
    + "Image Processing, vol. 10, no. 10, pp. 1593-1601, 2001.", { after: 80 }),
  p("[3] B. Chen and G. W. Wornell, \"Quantization index modulation: a class of "
    + "provably good methods for digital watermarking and information embedding,\" "
    + "IEEE Transactions on Information Theory, vol. 47, no. 4, pp. 1423-1443, 2001.",
    { after: 80 }),
  p("[4] R. C. Merkle, \"A digital signature based on a conventional encryption "
    + "function,\" Advances in Cryptology - CRYPTO '87, pp. 369-378, 1988.", { after: 80 }),
  p("[5] D. J. Bernstein, N. Duif, T. Lange, P. Schwabe and B.-Y. Yang, "
    + "\"High-speed high-security signatures,\" Journal of Cryptographic Engineering, "
    + "vol. 2, no. 2, pp. 77-89, 2012.", { after: 80 }),
  p("[6] M. Bellare, R. Canetti and H. Krawczyk, \"Keying hash functions for message "
    + "authentication,\" Advances in Cryptology - CRYPTO '96, pp. 1-15, 1996.", { after: 80 }),
  p("[7] H. He, J. Zhang and F. Chen, \"Adjacent-block based statistical detection "
    + "method for self-embedding watermarking techniques,\" Signal Processing, vol. 89, "
    + "no. 8, pp. 1557-1566, 2009.", { after: 80 }),
  p("[8] International Organization for Standardization, ISO/IEC 18004:2015, "
    + "\"Information technology - Automatic identification and data capture techniques "
    + "- QR Code bar code symbology specification.\"", { after: 80 }),
];

// ---------- document ----------
const doc = new Document({
  creator: "Ritik Rana",
  title: "QR-Linked Fragmented Watermarking for Tamper-Evident Document Authentication",
  description: "Project report",
  styles: {
    default: {
      document: { run: { font: BODY, size: 22, color: INK } },
    },
  },
  numbering: {
    config: [
      { reference: "dots", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 240 } } } }] },
      { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: { margin: { top: 1440, bottom: 1440, left: 1420, right: 1420 } },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 120 },
          children: [new TextRun({ children: [PageNumber.CURRENT],
            font: BODY, size: 20, color: INK })],
        })],
      }),
    },
    children: [...titlePage, ...front, ...body],
  }],
});

Packer.toBuffer(doc).then(b => {
  fs.writeFileSync("doc/QLFW_Project_Report.docx", b);
  console.log("wrote doc/QLFW_Project_Report.docx", (b.length / 1024).toFixed(0) + " KB");
});
