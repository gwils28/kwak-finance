import { type QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import type { Language } from "./api/generated";
import { I18nProvider } from "./i18n";
import type { createAppRouter } from "./router";

export function App({
  queryClient,
  router,
  language,
}: {
  queryClient: QueryClient;
  router: ReturnType<typeof createAppRouter>;
  language: Language;
}) {
  return (
    <I18nProvider initial={language}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </I18nProvider>
  );
}
