import { useState } from "react";
import { useI18n } from "../i18n";
import { DashFrame } from "./DashFrame";
import { ProjectionAssumptions } from "./ProjectionAssumptions";

/** The wealth projection (F-SIM-5): the Dash page, then the assumptions it reads. */
export function WealthProjectionPage() {
  const { t } = useI18n();
  // Each saved assumption loads the Dash page again, which reads them afresh.
  const [version, setVersion] = useState(0);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.wealth.projectionTitle}</h1>
      <DashFrame page="projection" title={t.wealth.projectionFrame} version={version} />
      <ProjectionAssumptions onSaved={() => setVersion((v) => v + 1)} />
    </div>
  );
}
