import { client } from "./generated/client.gen";

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const CSRF_COOKIE = "kwak_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const HOUSEHOLD_HEADER = "X-Kwak-Household";

/** The household the pages show: the API refuses a change meant for another one (F-ADM-5). */
let shownHousehold: string | null = null;

export function showHousehold(id: string | null): void {
  shownHousehold = id;
}

let interceptorInstalled = false;

function readCookie(name: string): string | undefined {
  const prefix = `${name}=`;
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(prefix))
    ?.slice(prefix.length);
}

/** Point the generated SDK at this origin and add the headers the API requires on changes. */
export function configureApiClient(): void {
  client.setConfig({ baseUrl: window.location.origin, credentials: "same-origin" });
  if (interceptorInstalled) return;
  interceptorInstalled = true;
  client.interceptors.request.use((request) => {
    const token = readCookie(CSRF_COOKIE);
    if (SAFE_METHODS.has(request.method)) return request;
    if (token) request.headers.set(CSRF_HEADER, token);
    if (shownHousehold) request.headers.set(HOUSEHOLD_HEADER, shownHousehold);
    return request;
  });
}
