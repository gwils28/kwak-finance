import { afterEach, expect, test, vi } from "vitest";
import { configureApiClient } from "./client";
import { logout, me } from "./generated";

function setCsrfCookie(value: string, maxAge?: number) {
  // biome-ignore lint/suspicious/noDocumentCookie: the client reads the cookie the API sets.
  document.cookie = `kwak_csrf=${value}${maxAge === undefined ? "" : `; max-age=${maxAge}`}`;
}

afterEach(() => {
  vi.unstubAllGlobals();
  setCsrfCookie("", 0);
});

function stubFetch() {
  const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetch);
  return () => fetch.mock.calls[0]?.[0] as Request;
}

test("unsafe requests echo the CSRF cookie in a header", async () => {
  configureApiClient();
  setCsrfCookie("token-123");
  const sent = stubFetch();

  await logout();

  expect(sent().headers.get("X-CSRF-Token")).toBe("token-123");
});

test("safe requests do not send the CSRF header", async () => {
  configureApiClient();
  setCsrfCookie("token-123");
  const sent = stubFetch();

  await me();

  expect(sent().headers.has("X-CSRF-Token")).toBe(false);
});

test("requests stay on the same origin and send the session cookie", async () => {
  configureApiClient();
  const sent = stubFetch();

  await me();

  expect(sent().credentials).toBe("same-origin");
  expect(new URL(sent().url).pathname).toBe("/api/auth/me");
});
