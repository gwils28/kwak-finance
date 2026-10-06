import { client } from "./generated/client.gen";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const CSRF_COOKIE = "kwak_csrf";
const CSRF_HEADER = "X-CSRF-Token";

let interceptorInstalled = false;

function readCookie(name: string): string | undefined {
  const prefix = `${name}=`;
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(prefix))
    ?.slice(prefix.length);
}

/** Point the generated SDK at this origin and add the CSRF header the API requires. */
export function configureApiClient(): void {
  client.setConfig({ baseUrl: window.location.origin, credentials: "same-origin" });
  if (interceptorInstalled) return;
  interceptorInstalled = true;
  client.interceptors.request.use((request) => {
    const token = readCookie(CSRF_COOKIE);
    if (token && !SAFE_METHODS.has(request.method)) request.headers.set(CSRF_HEADER, token);
    return request;
  });
}
