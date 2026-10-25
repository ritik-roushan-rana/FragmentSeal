#!/usr/bin/env bash
# Live demonstration. Takes any document the audience supplies:
#
#     ./present.sh                     # uses the generated sample certificate
#     ./present.sh ~/their-file.pdf    # uses a document chosen by the audience
#
# Nothing about the attack is fixed: the target region is chosen at random at
# run time, and step 5 hands the file to the audience to edit in any tool they
# like. The verifier is never told what changed, or that anything changed.
set -euo pipefail

PY=${PY:-.venv/bin/python}
OUT=${OUT:-out/present}
DOC=${1:-}
mkdir -p "$OUT"

pause() { echo; read -rp "   [Enter] to continue "; echo; }
rule()  { printf '\n\033[1m%s\033[0m\n' "$1"; printf '%.0s-' {1..70}; echo; }

if [ -z "$DOC" ]; then
    $PY make_sample.py >/dev/null
    DOC=samples/certificate.png
fi
echo "document under test: $DOC"

rule "1. Issue an issuer key"
echo "The HMAC half verifies pixels; the Ed25519 half attributes the document."
rm -f "$OUT/issuer.key"
$PY -m qlfw keygen --out "$OUT/issuer.key"
ISSUER=$($PY -c "from qlfw.keystore import KeyFile; print(KeyFile.load('$OUT/issuer.key').sign_pk.hex())")
pause

rule "2. Watermark the document"
echo "Each 32x32 fragment gets an authenticator for a DIFFERENT fragment."
EXT="${DOC##*.}"; [ "$EXT" = "pdf" ] || EXT=png
$PY -m qlfw embed "$DOC" "$OUT/signed.$EXT" --keyfile "$OUT/issuer.key"
pause

rule "3. Read the QR anchor, without the secret key"
echo "This is all the QR carries: parameters, a Merkle root, a signature."
$PY -m qlfw inspect "$OUT/signed.$EXT" --issuer "$ISSUER"
pause

rule "4. Verify the genuine document  (expect AUTHENTIC)"
$PY -m qlfw verify "$OUT/signed.$EXT" --keyfile "$OUT/issuer.key"
pause

rule "5. Verify with somebody else's key  (expect failure)"
echo "The watermark is meaningless without the key that produced it."
$PY -m qlfw keygen --out "$OUT/stranger.key" --force >/dev/null
$PY -m qlfw verify "$OUT/signed.$EXT" --keyfile "$OUT/stranger.key" || true
pause

rule "6. Forge it"
echo "Option A: edit  $OUT/signed.$EXT  yourself, in any editor, and save it"
echo "          as $OUT/forged.$EXT. Press Enter when you are done."
echo "Option B: press Enter with no such file and a random region is attacked."
read -rp "   [Enter] when ready "
if [ ! -f "$OUT/forged.$EXT" ]; then
    echo
    echo "no hand-made forgery found; attacking a region chosen at random:"
    $PY -m qlfw tamper "$OUT/signed.$EXT" "$OUT/forged.$EXT" \
        --mode text --rect random --text "VOID"
fi
pause

rule "7. Verify the forgery  (expect TAMPERED, and the location)"
echo "The verifier receives only the file and the key. It is not told what"
echo "changed, where, or even that anything did."
$PY -m qlfw verify "$OUT/forged.$EXT" --keyfile "$OUT/issuer.key" \
    --map "$OUT/tampermap.$EXT" --grid || true

echo
echo "tamper map: $OUT/tampermap.$EXT   (red = located edit, amber = guardian fallout)"
