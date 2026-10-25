#!/usr/bin/env bash
# End-to-end walkthrough: issue a document, forge it, catch the forgery.
set -euo pipefail

PY=${PY:-.venv/bin/python}
OUT=out
mkdir -p "$OUT"

$PY make_sample.py

echo "== issuing a key =="
rm -f "$OUT/issuer.key"
$PY -m qlfw keygen --out "$OUT/issuer.key"
ISSUER=$($PY -c "from qlfw.keystore import KeyFile; print(KeyFile.load('$OUT/issuer.key').sign_pk.hex())")

echo
echo "== watermarking =="
$PY -m qlfw embed samples/certificate.png "$OUT/certificate.wm.png" \
    --keyfile "$OUT/issuer.key" --note "NGU-2022-04417"

echo
echo "== the anchor, read without the secret key =="
$PY -m qlfw inspect "$OUT/certificate.wm.png" --issuer "$ISSUER"

echo
echo "== verifying the genuine document =="
$PY -m qlfw verify "$OUT/certificate.wm.png" --keyfile "$OUT/issuer.key"

echo
echo "== forging the CGPA =="
$PY -m qlfw tamper "$OUT/certificate.wm.png" "$OUT/certificate.forged.png" \
    --mode text --rect 325,492,230,34 --text "9.94 / 10.00"

echo
echo "== verifying the forgery =="
$PY -m qlfw verify "$OUT/certificate.forged.png" --keyfile "$OUT/issuer.key" \
    --map "$OUT/tampermap.png" --grid || true

echo
echo "tamper map written to $OUT/tampermap.png"
