/** The grid's JSON calls. Never follows a redirect into HTML: a 401 is
 *  "signed out", any other non-2xx carries an "error" sentence, and a
 *  network failure is its own message. */
import type { Changed, WindowJson } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
  get signedOut() { return this.status === 401; }
}

const UNREACHABLE = "The server couldn't be reached. Check your connection and try again.";

function csrf(): string {
  return (document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement | null)?.content ?? "";
}

async function answer<T>(p: Promise<Response>): Promise<T> {
  let r: Response;
  try { r = await p; } catch { throw new ApiError(0, UNREACHABLE); }
  if (r.status === 401) throw new ApiError(401, "Your session ended.");
  let body: unknown = null;
  try { body = await r.json(); } catch { /* not JSON */ }
  if (!r.ok) {
    const message = (body as { error?: string } | null)?.error || `That didn't work (HTTP ${r.status}).`;
    throw new ApiError(r.status, message);
  }
  return body as T;
}

export function getWindow(api: string, from: string, weeks: number, filters: string): Promise<WindowJson> {
  const q = new URLSearchParams(filters);
  q.set("from", from); q.set("weeks", String(weeks));
  return answer(fetch(`${api}window/?${q}`, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" }));
}

export function post<T = Changed>(api: string, path: string, body: unknown): Promise<T> {
  return answer(fetch(`${api}${path}`, {
    method: "POST", credentials: "same-origin", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
  }));
}
