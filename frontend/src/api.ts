// Session credentials stay in an HttpOnly cookie. Only the CSRF token is in memory.
localStorage.removeItem("searchroom.tokens");
let csrf: string | null = null;
let csrfRequest: Promise<string> | null = null;
const pending = new Set<AbortController>();
const channel =
  typeof BroadcastChannel === "undefined"
    ? null
    : new BroadcastChannel("searchroom.auth");
export function authChanged(broadcast = true) {
  csrf = null;
  submissions.clear();
  for (const controller of pending) controller.abort();
  pending.clear();
  if (broadcast) channel?.postMessage("changed");
  window.dispatchEvent(new Event("auth-change"));
}
channel?.addEventListener("message", () => authChanged(false));
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
async function csrfToken(): Promise<string> {
  if (csrf) return csrf;
  if (!csrfRequest)
    csrfRequest = fetch("/api/v1/auth/csrf", {
      credentials: "same-origin",
      signal: AbortSignal.timeout(15000),
    })
      .then(async (r) => {
        if (!r.ok)
          throw new ApiError(
            "Cannot establish a secure session. Retry shortly.",
            r.status,
          );
        return (await r.json()).csrf_token as string;
      })
      .then((value) => {
        csrf = value;
        return value;
      })
      .finally(() => {
        csrfRequest = null;
      });
  return csrfRequest;
}
// Retain submission IDs after network failure so an explicit retry is safe.
const submissions = new Map<string, string>();
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  authenticated = true,
  signal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  pending.add(controller);
  const timer = setTimeout(() => controller.abort(), 15000);
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  const fingerprint = path + JSON.stringify(body);
  const collaboration =
    method === "POST" && /\/(messages|updates|comments|feedback)$/.test(path);
  if (collaboration && !submissions.has(fingerprint))
    submissions.set(fingerprint, crypto.randomUUID());
  try {
    const token = method === "GET" ? null : await csrfToken();
    const response = await fetch(`/api/v1${path}`, {
      method,
      credentials: "same-origin",
      signal: controller.signal,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(token ? { "X-CSRF-Token": token } : {}),
        ...(collaboration
          ? { "Idempotency-Key": submissions.get(fingerprint)! }
          : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      if (response.status === 401 && authenticated) authChanged();
      const detail = payload?.detail;
      throw new ApiError(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg: string }) => d.msg).join(". ")
            : `Request failed (${response.status}). Please retry.`,
        response.status,
      );
    }
    if (collaboration) submissions.delete(fingerprint);
    if (path.startsWith("/auth/")) csrf = null;
    return response.status === 204 ? (undefined as T) : response.json();
  } finally {
    clearTimeout(timer);
    pending.delete(controller);
    signal?.removeEventListener("abort", abort);
  }
}
export interface Page<T> {
  items: T[];
  next_cursor: number | null;
}
