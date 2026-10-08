"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, apiGet, apiObjectUrl } from "./api";

interface Resource<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** Refetch; safe to call from event handlers and intervals. */
  reload: () => void;
}

function describe(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

/**
 * GET a backend resource and keep it in component state.
 *
 * State is only ever written from the fetch's own callbacks, never
 * synchronously inside the effect, which keeps React from cascading renders on
 * mount. Pass `path: null` to hold off until a dependency is known.
 */
export function useApiResource<T>(
  path: string | null,
  options: { auth?: boolean; errorMessage?: string; pollMs?: number } = {},
): Resource<T> {
  const { auth = true, errorMessage = "Could not load this data.", pollMs } = options;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!path) return;
    let active = true;
    apiGet<T>(path, { auth })
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setError(null);
        setLoading(false);
      })
      .catch((caught) => {
        if (!active) return;
        setError(describe(caught, errorMessage));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, auth, errorMessage, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    if (!pollMs) return;
    const timer = window.setInterval(reload, pollMs);
    return () => window.clearInterval(timer);
  }, [pollMs, reload]);

  return { data, error, loading, reload };
}

/**
 * Fetch an authenticated image (QR stamp, rendered page) and expose it as an
 * object URL, revoking the previous one as it goes.
 */
export function useAuthedImage(path: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!path) return;
    let active = true;
    let created: string | null = null;
    apiObjectUrl(path)
      .then((objectUrl) => {
        if (!active) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        created = objectUrl;
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setUrl(null);
      });
    return () => {
      active = false;
      if (created) URL.revokeObjectURL(created);
    };
  }, [path]);

  return url;
}
