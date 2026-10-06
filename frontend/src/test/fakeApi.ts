import { vi } from "vitest";

type Handler = (body: unknown, url: URL) => Response | Promise<Response>;

/** Stub `fetch` with handlers keyed by "METHOD /path". Unknown routes answer 404. */
export function fakeApi(handlers: Record<string, Handler>) {
  const calls: { route: string; body: unknown; headers: Headers }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const route = `${request.method} ${new URL(request.url).pathname}`;
      // Multipart bodies stay raw text: undici cannot parse them back under jsdom's File class.
      const isForm = request.headers.get("Content-Type")?.startsWith("multipart/form-data");
      const text = await request.text();
      const body: unknown = isForm ? text : text ? JSON.parse(text) : undefined;
      calls.push({ route, body, headers: request.headers });
      const handler = handlers[route];
      const url = new URL(request.url);
      return handler ? handler(body, url) : Response.json({ detail: "not found" }, { status: 404 });
    }),
  );
  return calls;
}

export const owner = {
  id: "0192f0a0-0000-7000-8000-000000000001",
  household_id: "0192f0a0-0000-7000-8000-000000000002",
  email: "owner@example.com",
  display_name: "Wilson",
  role: "owner",
  language: "en",
};

export const unauthenticated = () =>
  Response.json({ detail: "not authenticated" }, { status: 401 });
