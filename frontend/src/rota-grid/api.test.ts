import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ApiError, getWindow, post } from "./api";

// api.ts needs only fetch and Response (both in Node) and the csrf meta tag,
// which a stubbed document answers; no DOM is involved.
const fetchMock = vi.fn();
beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("document", { querySelector: () => ({ content: "tok" }) });
});
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals(); });

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const caught = async (p: Promise<unknown>) => { try { await p; } catch (e) { return e as ApiError; } throw new Error("did not throw"); };

it("both calls refuse to follow redirects, and post sends the token", async () => {
  fetchMock.mockImplementation(() => Promise.resolve(json({})));
  await getWindow("/rota/api/", "2027-03-01", 1, "team=2");
  await post("/rota/api/", "clear/", { cells: [] });
  expect(fetchMock.mock.calls[0][0]).toBe("/rota/api/window/?team=2&from=2027-03-01&weeks=1");
  expect(fetchMock.mock.calls[0][1].redirect).toBe("manual");
  expect(fetchMock.mock.calls[1][1].redirect).toBe("manual");
  expect(fetchMock.mock.calls[1][1].headers["X-CSRFToken"]).toBe("tok");
});

it("a 401 is signed out", async () => {
  fetchMock.mockResolvedValue(json({ error: "signed out" }, 401));
  const e = await caught(post("/rota/api/", "clear/", {}));
  expect(e.signedOut).toBe(true);
});

it("an opaque redirect is signed out too", async () => {
  const redirect = { type: "opaqueredirect", status: 0, ok: false, json: () => Promise.reject(new Error("no body")) };
  fetchMock.mockResolvedValue(redirect);
  const e = await caught(post("/rota/api/", "clear/", {}));
  expect(e.signedOut).toBe(true);
  expect(e.message).toBe("Your session ended.");
});

it("a 2xx that is not JSON is an error, not a null result", async () => {
  fetchMock.mockResolvedValue(new Response("<html></html>", { status: 200 }));
  const e = await caught(post("/rota/api/", "clear/", {}));
  expect(e.signedOut).toBe(false);
  expect(e.message).toBe("The server answered with something other than JSON.");
});

it("another failure carries the server's sentence, or the status", async () => {
  fetchMock.mockResolvedValueOnce(json({ error: "Not yours to edit." }, 403));
  expect((await caught(post("/rota/api/", "clear/", {}))).message).toBe("Not yours to edit.");
  fetchMock.mockResolvedValueOnce(new Response("<html>", { status: 500 }));
  expect((await caught(post("/rota/api/", "clear/", {}))).message).toBe("That didn't work (HTTP 500).");
});

it("a network failure is its own message", async () => {
  fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
  const e = await caught(getWindow("/rota/api/", "2027-03-01", 1, ""));
  expect(e.status).toBe(0);
  expect(e.message).toMatch(/couldn't be reached/);
});
