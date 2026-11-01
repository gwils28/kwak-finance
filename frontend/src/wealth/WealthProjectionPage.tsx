import { useI18n } from "../i18n";
import { ProjectionSimulator } from "./ProjectionSimulator";

/** The wealth projection (F-SIM-5): a simulator in the app, its charts drawn with Recharts. */
export function WealthProjectionPage() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.projection.title}</h1>
      <ProjectionSimulator />
    </div>
  );
}
