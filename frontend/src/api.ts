import type { Tokens } from "./types";
const KEY = "searchroom.tokens";
export function tokens(): Tokens | null {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "null");
  } catch {
    return null;
  }
}
export function saveTokens(value: Tokens | null) {
  if (value) localStorage.setItem(KEY, JSON.stringify(value));
  else localStorage.removeItem(KEY);
  window.dispatchEvent(new Event("auth-change"));
}
async function responseError(response: Response) {
  const body = await response.json().catch(() => null);
  const detail = body?.detail;
  return new Error(
    typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: { msg: string }) => d.msg).join(". ")
        : `Request failed (${response.status}). Please try again.`,
  );
}
let refreshing: Promise<void> | null = null;
async function refresh(previous: string) {
  const work = async () => {
    const current = tokens();
    if (!current) throw new Error("Please sign in again.");
    if (current.access_token !== previous) return;
    const res = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: current.refresh_token }),
    });
    if (!res.ok) {
      if (res.status === 401) saveTokens(null);
      throw await responseError(res);
    }
    saveTokens(await res.json());
  };
  if (!refreshing) {
    // Serialize refresh across browser tabs as well as requests in this tab.
    refreshing = Promise.resolve(
      navigator.locks
        ? navigator.locks.request("searchroom-refresh", work)
        : work(),
    )
      .then(() => {})
      .finally(() => {
        refreshing = null;
      });
  }
  await refreshing;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  authenticated = true,
): Promise<T> {
  const send = () =>
    fetch(`/api/v1${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(authenticated && tokens()
          ? { Authorization: `Bearer ${tokens()!.access_token}` }
          : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  const previous = tokens()?.access_token;
  let response = await send();
  if (response.status === 401 && authenticated && previous) {
    await refresh(previous);
    response = await send();
    if (response.status === 401) saveTokens(null);
  }
  if (!response.ok) throw await responseError(response);
  return response.status === 204 ? (undefined as T) : response.json();
}
