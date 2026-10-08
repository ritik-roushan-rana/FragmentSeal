"use client";

import Link from "next/link";
import {
  Camera,
  CameraOff,
  CheckCircle2,
  ClipboardPaste,
  FileSearch,
  ImageUp,
  QrCode,
  XCircle,
} from "lucide-react";
import jsQR from "jsqr";
import { useCallback, useEffect, useRef, useState } from "react";

import { Badge, verdictTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Textarea } from "@/components/ui/input";
import { Alert, Mono, StatRow } from "@/components/ui/misc";
import { ApiError, apiPost } from "@/lib/api";
import type { QrLookupResult } from "@/lib/types";
import { formatDateTime, shortHash } from "@/lib/utils";

export default function ScanPage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const [scanning, setScanning] = useState(false);
  const [raw, setRaw] = useState("");
  const [result, setResult] = useState<QrLookupResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const lookup = useCallback(async (text: string) => {
    setBusy(true);
    setError(null);
    try {
      const response = await apiPost<QrLookupResult>(
        "/verify/qr",
        { raw: text },
        { auth: false },
      );
      setResult(response);
    } catch (caught) {
      setResult(null);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not check that payload against the register.",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setScanning(false);
  }, []);

  // Release the camera if the page unmounts while it is open.
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    };
  }, []);

  // The decode loop lives in an effect keyed on `scanning`, so starting and
  // stopping the camera is just a state change and the animation frame is
  // always cancelled on cleanup.
  useEffect(() => {
    if (!scanning) return;
    let frame = 0;
    let cancelled = false;

    const decode = () => {
      if (cancelled) return;
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState !== video.HAVE_ENOUGH_DATA) {
        frame = requestAnimationFrame(decode);
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) return;
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      const image = context.getImageData(0, 0, canvas.width, canvas.height);
      const code = jsQR(image.data, image.width, image.height, {
        inversionAttempts: "attemptBoth",
      });
      if (code?.data) {
        setRaw(code.data);
        void lookup(code.data);
        stop();
        return;
      }
      frame = requestAnimationFrame(decode);
    };

    frame = requestAnimationFrame(decode);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [scanning, lookup, stop]);

  async function start() {
    setError(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setScanning(true);
    } catch {
      setError(
        "Could not open the camera. Grant camera permission, or paste the payload / upload a photo below.",
      );
    }
  }

  async function onImage(file: File) {
    setError(null);
    const bitmap = await createImageBitmap(file);
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d");
    if (!context) return;
    context.drawImage(bitmap, 0, 0);
    const image = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(image.data, image.width, image.height, {
      inversionAttempts: "attemptBoth",
    });
    if (!code?.data) {
      setError("No QR code could be found in that image. Try a closer, sharper photo.");
      return;
    }
    setRaw(code.data);
    void lookup(code.data);
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Scan a QR code</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted">
            Reads the stamp on a protected document and checks its signature and status
            against the issuing register.
          </p>
        </div>
        <Link href="/verify">
          <Button variant="outline" icon={<FileSearch className="size-4" />}>
            Upload the file instead
          </Button>
        </Link>
      </div>

      <Alert tone="info" className="mt-6">
        A QR scan proves <strong>provenance</strong>: that this authority signed this Merkle root
        for this document ID, and whether it is still valid. It cannot prove the document in your
        hand still matches that root — upload the file for integrity checking.
      </Alert>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Camera"
            description="Point the rear camera at the QR stamp in the document footer."
            icon={<Camera className="size-4" />}
            action={
              scanning ? (
                <Button
                  size="sm"
                  variant="danger"
                  icon={<CameraOff className="size-3.5" />}
                  onClick={stop}
                >
                  Stop
                </Button>
              ) : (
                <Button size="sm" icon={<Camera className="size-3.5" />} onClick={start}>
                  Start camera
                </Button>
              )
            }
          />
          <CardBody>
            <div className="relative aspect-[4/3] overflow-hidden rounded-lg bg-black">
              <video
                ref={videoRef}
                playsInline
                muted
                className="size-full object-cover"
                aria-label="Camera preview"
              />
              {scanning ? (
                <>
                  <div className="pointer-events-none absolute inset-[12%] rounded-xl border-2 border-white/70" />
                  <span className="animate-scan pointer-events-none absolute inset-x-[12%] top-[12%] h-0.5 bg-[var(--brand)]" />
                </>
              ) : (
                <div className="absolute inset-0 grid place-items-center text-center">
                  <div className="text-white/70">
                    <QrCode className="mx-auto size-10" />
                    <p className="mt-2 text-xs">Camera is off</p>
                  </div>
                </div>
              )}
            </div>
            <canvas ref={canvasRef} className="hidden" />

            <div className="mt-4 space-y-3">
              <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--border-strong)] px-4 py-3 text-xs font-medium text-muted transition-colors hover:border-brand hover:text-foreground">
                <ImageUp className="size-4" />
                Upload a photo or screenshot of the QR code
                <input
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void onImage(file);
                    event.target.value = "";
                  }}
                />
              </label>

              <Field
                label="Or paste the payload"
                hint="The JSON string encoded in the QR code."
                htmlFor="raw"
              >
                <Textarea
                  id="raw"
                  value={raw}
                  onChange={(event) => setRaw(event.target.value)}
                  placeholder='{"v":1,"id":"…","r":"…","t":"…","s":"…","k":"…","a":"ES256"}'
                  className="font-mono text-[11px]"
                />
              </Field>
              <Button
                className="w-full"
                variant="secondary"
                loading={busy}
                disabled={!raw.trim()}
                icon={<ClipboardPaste className="size-4" />}
                onClick={() => lookup(raw.trim())}
              >
                Check this payload
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Register lookup"
            description="What the issuing authority says about this document."
            icon={<QrCode className="size-4" />}
          />
          <CardBody>
            {error ? <Alert tone="bad">{error}</Alert> : null}

            {!error && !result ? (
              <p className="grid h-56 place-items-center text-center text-xs text-muted">
                Scan, upload or paste a QR payload to see its issuance record.
              </p>
            ) : null}

            {result ? (
              <div className="space-y-4">
                <div
                  className={`flex items-start gap-3 rounded-lg px-4 py-3 ${
                    result.verdict === "valid"
                      ? "bg-[var(--ok-soft)] text-[var(--ok)]"
                      : result.verdict === "revoked"
                        ? "bg-[var(--warn-soft)] text-[var(--warn)]"
                        : "bg-[var(--bad-soft)] text-[var(--bad)]"
                  }`}
                >
                  {result.verdict === "valid" ? (
                    <CheckCircle2 className="mt-0.5 size-5 shrink-0" />
                  ) : (
                    <XCircle className="mt-0.5 size-5 shrink-0" />
                  )}
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-wide">
                      {result.verdict}
                    </p>
                    <p className="mt-0.5 text-xs opacity-90">
                      {result.verdict === "valid"
                        ? "Signature validates and the root matches the register."
                        : result.verdict === "revoked"
                          ? result.document?.revoked_reason ??
                            "The issuer has withdrawn this document."
                          : result.registered
                            ? "The payload does not match this document's issuance record."
                            : "This document ID is not in the issuing register."}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge tone={result.signature_valid ? "ok" : "bad"}>
                    signature {result.signature_valid ? "valid" : "invalid"}
                  </Badge>
                  <Badge tone={result.registered ? "ok" : "bad"}>
                    {result.registered ? "in register" : "unregistered"}
                  </Badge>
                  <Badge tone={result.root_matches_register ? "ok" : "bad"}>
                    root {result.root_matches_register ? "matches" : "differs"}
                  </Badge>
                  {result.document ? (
                    <Badge tone={verdictTone[result.document.status] ?? "neutral"}>
                      {result.document.status}
                    </Badge>
                  ) : null}
                </div>

                <div>
                  <StatRow label="Document ID" value={result.payload.document_id} mono />
                  <StatRow label="Document" value={result.document?.name ?? "—"} />
                  <StatRow label="Subject" value={result.document?.subject ?? "—"} />
                  <StatRow label="Issuer" value={result.document?.issuer ?? "—"} />
                  <StatRow label="Issued" value={formatDateTime(result.payload.issued_at)} />
                  <StatRow
                    label="Merkle root"
                    value={<Mono>{shortHash(result.payload.merkle_root, 14, 8)}</Mono>}
                  />
                  <StatRow label="Algorithm" value={result.payload.algorithm} />
                  <StatRow label="Key ID" value={<Mono>{result.payload.key_id || "—"}</Mono>} />
                  <StatRow
                    label="Fragments"
                    value={result.document?.fragment_count ?? "—"}
                  />
                </div>

                <p className="text-[11px] leading-relaxed text-muted">{result.note}</p>

                <Link href="/verify">
                  <Button className="w-full" icon={<FileSearch className="size-4" />}>
                    Upload the file to check its contents
                  </Button>
                </Link>
              </div>
            ) : null}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
