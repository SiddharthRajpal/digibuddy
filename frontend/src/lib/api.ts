/**
 * Small fetch client for the DigiBuddy API.
 *
 * - The access token lives in memory only. The refresh token is an httpOnly cookie
 *   that the browser sends to /api/v1/auth/* automatically.
 * - On a 401 the client refreshes once and retries the request.
 */
import type { TokenResponse } from "@/types/api";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type Listener = (token: string | null) => void;

let accessToken: string | null = null;
const listeners = new Set<Listener>();
let refreshing: Promise<TokenResponse | null> | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
  listeners.forEach((l) => l(token));
}

export function onTokenChange(l: Listener): () => void {
  listeners.add(l);
  return () => listeners.delete(l);
}

function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: string };
      if (first?.msg) return first.msg.replace(/^Value error, /, "");
    }
  }
  return fallback;
}

async function parse(res: Response): Promise<unknown> {
  if (res.status === 204) return null;
  const type = res.headers.get("content-type") ?? "";
  if (type.includes("application/json")) return res.json();
  return res.text();
}

/** Ask for a fresh access token using the refresh cookie. Deduplicates concurrent calls. */
export async function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
        });
        if (!res.ok) {
          setAccessToken(null);
          return null;
        }
        const data = (await res.json()) as TokenResponse;
        setAccessToken(data.access_token);
        return data;
      } catch {
        setAccessToken(null);
        return null;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  auth?: boolean;
  signal?: AbortSignal;
  raw?: boolean;
}

export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, signal, raw = false } = opts;

  const send = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers.Authorization = `Bearer ${accessToken}`;
    return fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include",
      signal,
    });
  };

  let res = await send();
  if (res.status === 401 && auth) {
    const refreshed = await refreshSession();
    if (refreshed) res = await send();
  }
  if (raw && res.ok) return res as unknown as T;
  const data = await parse(res);
  if (!res.ok) {
    throw new ApiError(res.status, messageFrom(data, "Something went wrong. Please try again."), data);
  }
  return data as T;
}
