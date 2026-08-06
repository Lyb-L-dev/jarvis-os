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

export async function request<T>(
  url: string | URL,
  options: RequestOptions,
): Promise<T> {
  const init: RequestInit = { method: options.method ?? "GET" };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  if (options.cache !== undefined) {
    init.cache = options.cache;
  }
  if (options.signal !== undefined) {
    init.signal = options.signal;
  }
  const response = await fetch(url, init);
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
  const init: RequestInit = { method: options.method ?? "GET" };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  if (options.cache !== undefined) {
    init.cache = options.cache;
  }
  if (options.signal !== undefined) {
    init.signal = options.signal;
  }
  const response = await fetch(url, init);
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
