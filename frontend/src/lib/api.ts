/**
 * Thin typed client for the FastAPI backend.
 *
 * Access tokens are short-lived; a 401 triggers one silent refresh attempt
 * using the stored refresh token before the error is surfaced.
 */
import type { TokenPair } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://127.0.0.1:8000";
export const API = `${API_BASE}/api/v1`;

const ACCESS_KEY = "docauth.access";
const REFRESH_KEY = "docauth.refresh";
const USER_KEY = "docauth.user";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export const tokenStore = {
  access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  save(pair: TokenPair) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    window.localStorage.setItem(USER_KEY, JSON.stringify(pair.user));
  },
  user<T>(): T | null {
    if (typeof window === "undefined") return null;
    const raw = window.localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  },
  clear() {
    if (typeof window === "undefined") return;
    [ACCESS_KEY, REFRESH_KEY, USER_KEY].forEach((key) =>
      window.localStorage.removeItem(key),
    );
  },
};

async function readError(response: Response): Promise<ApiError> {
  let detail: unknown;
  let message = `${response.status} ${response.statusText}`;
  try {
    const body = await response.json();
    detail = body;
    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((item: { loc?: string[]; msg?: string }) =>
          [item.loc?.slice(1).join("."), item.msg].filter(Boolean).join(": "),
        )
        .join("; ");
    }
  } catch {
    // keep the status line
  }
  return new ApiError(message, response.status, detail);
}

async function refreshTokens(): Promise<boolean> {
  const refresh = tokenStore.refresh();
  if (!refresh) return false;
  const response = await fetch(`${API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!response.ok) {
    tokenStore.clear();
    return false;
  }
  tokenStore.save((await response.json()) as TokenPair);
  return true;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  auth?: boolean;
  raw?: boolean;
}

async function send(path: string, options: RequestOptions, retry = true): Promise<Response> {
  const { body, auth = true, raw, headers, ...rest } = options;
  const requestHeaders = new Headers(headers);

  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }

  if (auth) {
    const token = tokenStore.access();
    if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API}${path}`, {
    ...rest,
    headers: requestHeaders,
    body: payload,
  });

  if (response.status === 401 && auth && retry && (await refreshTokens())) {
    return send(path, options, false);
  }
  if (!response.ok) throw await readError(response);
  void raw;
  return response;
}

export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, { ...options, method: "GET" });
  return (await response.json()) as T;
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  const response = await send(path, { ...options, method: "POST", body });
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiDelete(path: string, options: RequestOptions = {}): Promise<void> {
  await send(path, { ...options, method: "DELETE" });
}

/** Fetch a binary endpoint (PDF / PNG) as a blob. */
export async function apiBlob(
  path: string,
  options: RequestOptions = {},
): Promise<{ blob: Blob; response: Response }> {
  const response = await send(path, { ...options, method: options.method ?? "GET" });
  return { blob: await response.blob(), response };
}

/** Fetch a protected image and return an object URL for an <img> tag. */
export async function apiObjectUrl(path: string): Promise<string> {
  const { blob } = await apiBlob(path);
  return URL.createObjectURL(blob);
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Give the browser a tick to start the download before revoking.
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const pair = await apiPost<TokenPair>("/auth/login", { email, password }, { auth: false });
  tokenStore.save(pair);
  return pair;
}

export async function register(input: {
  name: string;
  email: string;
  password: string;
  organization?: string;
}): Promise<TokenPair> {
  const pair = await apiPost<TokenPair>("/auth/register", input, { auth: false });
  tokenStore.save(pair);
  return pair;
}
