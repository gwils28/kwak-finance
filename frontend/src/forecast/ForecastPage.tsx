import { useI18n } from "../i18n";
import { DashFrame } from "../wealth/DashFrame";

/** The cash-flow forecast (F-FCT-6): a Dash page, which only reads. */
export function ForecastPage() {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{t.forecast.title}</h1>
      <DashFrame page="forecast" title={t.forecast.frame} version={0} />
    </div>
  );
}
