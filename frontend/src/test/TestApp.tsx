import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory } from "@tanstack/react-router";
import { useState } from "react";
import { App } from "../App";
import { configureApiClient } from "../api/client";
import type { Language } from "../api/generated";
import { createAppRouter } from "../router";

/** The whole app, starting at `path`, with a fresh cache: what a user sees on a cold load. */
/** `language` defaults to English, so tests read English texts and formats. */
export function TestApp({ path, language = "en" }: { path: string; language?: Language }) {
  const [app] = useState(() => {
    configureApiClient();
    const queryClient = new QueryClient();
    const history = createMemoryHistory({ initialEntries: [path] });
    return { queryClient, router: createAppRouter(queryClient, history) };
  });
  return <App queryClient={app.queryClient} router={app.router} language={language} />;
}
