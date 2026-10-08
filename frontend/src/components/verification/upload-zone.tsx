"use client";

import { FileText, UploadCloud, X } from "lucide-react";
import { useCallback, useRef, useState, type DragEvent } from "react";

import { Button } from "@/components/ui/button";
import { cn, formatBytes } from "@/lib/utils";

export function UploadZone({
  files,
  onChange,
  multiple = false,
  disabled = false,
  hint = "PDF only · up to 25 MB",
}: {
  files: File[];
  onChange: (files: File[]) => void;
  multiple?: boolean;
  disabled?: boolean;
  hint?: string;
}) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const accept = useCallback(
    (incoming: FileList | null) => {
      if (!incoming) return;
      const pdfs = Array.from(incoming).filter(
        (file) => file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf"),
      );
      onChange(multiple ? [...files, ...pdfs] : pdfs.slice(0, 1));
    },
    [files, multiple, onChange],
  );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (!disabled) accept(event.dataTransfer.files);
  };

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "relative rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-brand bg-brand-soft"
            : "border-[var(--border-strong)] bg-surface-muted/50",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <span className="mx-auto grid size-12 place-items-center rounded-xl bg-brand-soft text-brand">
          <UploadCloud className="size-6" />
        </span>
        <p className="mt-3 text-sm font-medium">
          Drop {multiple ? "PDF files" : "a PDF"} here, or{" "}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="cursor-pointer text-brand underline underline-offset-2"
          >
            browse
          </button>
        </p>
        <p className="mt-1 text-xs text-muted">{hint}</p>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple={multiple}
          className="hidden"
          onChange={(event) => {
            accept(event.target.files);
            event.target.value = "";
          }}
        />
      </div>

      {files.length ? (
        <ul className="mt-3 space-y-2">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-surface px-3 py-2"
            >
              <FileText className="size-4 shrink-0 text-brand" />
              <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
              <span className="shrink-0 text-xs text-muted">{formatBytes(file.size)}</span>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove ${file.name}`}
                onClick={() => onChange(files.filter((_, i) => i !== index))}
              >
                <X className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
