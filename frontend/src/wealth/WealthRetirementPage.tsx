import { useState } from "react";
import { useI18n } from "../i18n";
import { DashFrame } from "./DashFrame";
import { RetirementForm } from "./RetirementForm";

/** Retirement (F-RET-4): the Dash page, then the members' retirements and the settings. */
export function WealthRetirementPage() {
  const { t } = useI18n();
  const [version, setVersion] = useState(0);
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.wealth.retirementTitle}</h1>
      <DashFrame page="retirement" title={t.wealth.retirementFrame} version={version} />
      <RetirementForm onSaved={() => setVersion((v) => v + 1)} />
    </div>
  );
}
