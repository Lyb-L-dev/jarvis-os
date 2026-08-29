/**
 * Shared API client infrastructure (Sprint 4).
 * Owned by Frontend API Layer; do not import from components directly.
 */

export type RequestMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  method?: RequestMethod;
  body?: unknown;
  signal?: AbortSignal;
  cache?: RequestCache;
  action?: string;
  errorMessage?: (status: number) => string;
}

type DesktopRuntimeConnection = {
  apiBaseUrl: string;
  sessionToken?: string | null;
  runtimeMode: "source" | "bundled" | string;
  appVersion: string;
};

declare global {
  interface Window {
    __JARVIS_RUNTIME__?: DesktopRuntimeConnection;
  }
}

export function getRuntimeConnection(): DesktopRuntimeConnection | null {
  return typeof window === "undefined" ? null : (window.__JARVIS_RUNTIME__ ?? null);
}

export function getApiBaseUrl(): string {
  return getRuntimeConnection()?.apiBaseUrl ?? API_BASE_URL;
}

export function runtimeRequestHeaders(): HeadersInit {
  const token = getRuntimeConnection()?.sessionToken;
  return token ? { "X-Jarvis-Desktop-Session": token } : {};
}

export function apiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

export function runtimeUrl(url: string | URL): string | URL {
  const connection = getRuntimeConnection();
  if (!connection) return url;
  const value = url.toString();
  if (!value.startsWith(API_BASE_URL)) return url;
  return `${connection.apiBaseUrl}${value.slice(API_BASE_URL.length)}`;
}

export async function request<T>(
  url: string | URL,
  options: RequestOptions,
): Promise<T> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: runtimeRequestHeaders(),
  };
  if (options.body !== undefined) {
    init.headers = {
      ...runtimeRequestHeaders(),
      "Content-Type": "application/json",
    };
    init.body = JSON.stringify(options.body);
  }
  if (options.cache !== undefined) {
    init.cache = options.cache;
  }
  if (options.signal !== undefined) {
    init.signal = options.signal;
  }
  const response = await fetch(runtimeUrl(url), init);
  if (!response.ok) {
    if (options.errorMessage) {
      throw new Error(options.errorMessage(response.status));
    }
    throw await responseError(response, options.action ?? "Request");
  }
  return response.json() as Promise<T>;
}

export async function requestVoid(
  url: string | URL,
  options: RequestOptions,
): Promise<void> {
  const init: RequestInit = {
    method: options.method ?? "GET",
    headers: runtimeRequestHeaders(),
  };
  if (options.body !== undefined) {
    init.headers = {
      ...runtimeRequestHeaders(),
      "Content-Type": "application/json",
    };
    init.body = JSON.stringify(options.body);
  }
  if (options.cache !== undefined) {
    init.cache = options.cache;
  }
  if (options.signal !== undefined) {
    init.signal = options.signal;
  }
  const response = await fetch(runtimeUrl(url), init);
  if (!response.ok) {
    if (options.errorMessage) {
      throw new Error(options.errorMessage(response.status));
    }
    throw await responseError(response, options.action ?? "Request");
  }
}


export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export async function responseError(response: Response, action: string): Promise<Error> {
  let detail = "";
  try {
    const body = (await response.json()) as { detail?: string };
    detail = body.detail ? `: ${body.detail}` : "";
  } catch {
    // The status code still gives a useful fallback when a response is not JSON.
  }
  return new Error(`${action} failed with ${response.status}${detail}`);
}
