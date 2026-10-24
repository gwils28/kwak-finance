import { useI18n } from "../i18n";
import { useDocumentTheme } from "../theme";

/**
 * The wealth projection (F-SIM-5): an embedded Dash page (ARCHITECTURE, Dash integration), in
 * the app's language and theme. Its own strings live with it, in kwak_api/dash/i18n.py.
 */
export function WealthProjectionPage() {
  const { t, language } = useI18n();
  const theme = useDocumentTheme();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.wealth.projectionTitle}</h1>
      <iframe
        title={t.wealth.projectionFrame}
        src={`/dash/projection?lang=${language}&theme=${theme}`}
        className="h-[85vh] min-h-[36rem] w-full rounded-lg border border-border bg-bg"
      />
    </div>
  );
}
