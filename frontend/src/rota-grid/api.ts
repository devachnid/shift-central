/** The grid's JSON calls. Never follows a redirect into HTML: a 401 or a
 *  redirect is "signed out", any other non-2xx carries an "error" sentence,
 *  a 2xx that is not JSON is an error, and a network failure is its own
 *  message. */
import type { Changed, WindowJson } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
  get signedOut() { return this.status === 401; }
}

const UNREACHABLE = "The server couldn't be reached. Check your connection and try again.";

function csrf(): string {
  return (document.querySelector('meta[name="csrf-token"]') as HTMLMetaElement | null)?.content ?? "";
}

const NOT_JSON = "The server answered with something other than JSON.";

async function answer<T>(p: Promise<Response>): Promise<T> {
  let r: Response;
  try { r = await p; } catch { throw new ApiError(0, UNREACHABLE); }
  // Both calls use redirect: "manual", so a redirect (a user who lost their
  // Person is sent to a page, not to JSON) arrives as an opaque response
  // with status 0: treat it as signed out rather than follow it into HTML.
  if (r.type === "opaqueredirect" || r.status === 0 || r.status === 401) throw new ApiError(401, "Your session ended.");
  let body: unknown = null;
  let isJson = true;
  try { body = await r.json(); } catch { isJson = false; }
  if (!r.ok) {
    const message = (body as { error?: string } | null)?.error || `That didn't work (HTTP ${r.status}).`;
    throw new ApiError(r.status, message);
  }
  if (!isJson) throw new ApiError(r.status, NOT_JSON);
  return body as T;
}

export function getWindow(api: string, from: string, weeks: number, filters: string): Promise<WindowJson> {
  const q = new URLSearchParams(filters);
  q.set("from", from); q.set("weeks", String(weeks));
  return answer(fetch(`${api}window/?${q}`, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin", redirect: "manual" }));
}

export function post<T = Changed>(api: string, path: string, body: unknown): Promise<T> {
  return answer(fetch(`${api}${path}`, {
    method: "POST", credentials: "same-origin", redirect: "manual", body: JSON.stringify(body),
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
  }));
}
