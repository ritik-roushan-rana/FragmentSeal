"use client";

import { useParams } from "next/navigation";
import { useMemo } from "react";

import { Alert, Skeleton } from "@/components/ui/misc";
import { ResultView } from "@/components/verification/result-view";
import type { VerificationLog, VerificationResult } from "@/lib/types";
import { useApiResource } from "@/lib/use-api";

export default function VerificationResultPage() {
  const params = useParams<{ logId: string }>();
  const logId = params?.logId;
  const { data, error } = useApiResource<{ log: VerificationLog; result: VerificationResult }>(
    logId ? `/verify/logs/${logId}` : null,
    { auth: false, errorMessage: "Could not load that verification record." },
  );

  const result = useMemo(
    () => (data ? { ...data.result, log_id: data.log.id } : null),
    [data],
  );

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      {error ? (
        <Alert tone="bad" title="Record unavailable">
          {error}
        </Alert>
      ) : !result ? (
        <div className="space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-36 w-full" />
          <div className="grid gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, index) => (
              <Skeleton key={index} className="h-28 w-full" />
            ))}
          </div>
          <Skeleton className="h-96 w-full" />
        </div>
      ) : (
        <ResultView result={result} />
      )}
    </div>
  );
}
