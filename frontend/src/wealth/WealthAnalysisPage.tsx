import { ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { WealthCharts } from "./WealthCharts";
import { Summary, useWealthView, ViewControls } from "./WealthView";

/** The wealth analysis (F-WLT-6): the summary and the charts, over the months chosen. */
export function WealthAnalysisPage() {
  const { t } = useI18n();
  const view = useWealthView();
  const { matrix } = view;
  const data = matrix.data;
  const empty = data?.categories.every((c) => c.lines.length === 0);
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.wealth.analysisTitle}</h1>
          <p className="max-w-2xl text-sm text-muted">{t.wealth.analysisIntro}</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <ViewControls view={view} />
        </div>
      </div>
      {matrix.isError && <ErrorAlert message={t.wealth.loadFailed} />}
      {matrix.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {data && empty && <p className="text-sm">{t.wealth.empty}</p>}
      {data && !empty && <Summary matrix={data} />}
      {data && !empty && <WealthCharts matrix={data} />}
    </div>
  );
}
