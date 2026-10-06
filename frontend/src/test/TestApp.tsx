import { QueryClient } from "@tanstack/react-query";
import { createMemoryHistory } from "@tanstack/react-router";
import { useState } from "react";
import { App } from "../App";
import { configureApiClient } from "../api/client";
import { createAppRouter } from "../router";

/** The whole app, starting at `path`, with a fresh cache: what a user sees on a cold load. */
export function TestApp({ path }: { path: string }) {
  const [app] = useState(() => {
    configureApiClient();
    const queryClient = new QueryClient();
    const history = createMemoryHistory({ initialEntries: [path] });
    return { queryClient, router: createAppRouter(queryClient, history) };
  });
  return <App queryClient={app.queryClient} router={app.router} />;
}
