import { useI18n } from "../i18n";
import { useDocumentTheme } from "../theme";

/**
 * An embedded Dash page (ARCHITECTURE, Dash integration), in the app's language and theme;
 * its own strings live with it, in kwak_api/dash/i18n.py. A new `version` loads it again.
 */
export function DashFrame({
  page,
  title,
  version,
}: {
  page: string;
  title: string;
  version: number;
}) {
  const { language } = useI18n();
  const theme = useDocumentTheme();
  return (
    <iframe
      key={version}
      title={title}
      src={`/dash/${page}?lang=${language}&theme=${theme}`}
      className="h-[85vh] min-h-[36rem] w-full rounded-lg border border-border bg-bg"
    />
  );
}
