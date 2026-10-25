import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { goalAnalysis, type Scope } from "../api/generated";
import { ScopeSelect } from "../components/ScopeSelect";
import { ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { monthLabel } from "../lib/months";
import { Forward, RiskChart, StatusGrid, Timeline } from "./AnalysisCharts";
import { GoalChances } from "./GoalChances";
import { MoneySankey } from "./MoneySankey";
import { Points } from "./Points";
import { GOALS_KEY } from "./shared";

const labelClass = "flex flex-col gap-1 text-sm font-medium";
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

export function goalAnalysisQuery(scope: Scope, horizon: number, allAssets = false) {
  return {
    queryKey: [...GOALS_KEY, "analysis", scope, horizon, allAssets],
    queryFn: async () =>
      (
        await goalAnalysis({
          query: { scope, horizon, all_assets: allAssets },
          throwOnError: true,
        })
      ).data,
    placeholderData: keepPreviousData,
  };
}

/** The goals space's Analysis tab (spec §4.12): the points to look at, then the goals against
 * the capacity, on a timeline, by risk, where their money sits and month by month. */
export function AnalysisPage({ initialScope = "household" }: { initialScope?: Scope }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  // The Pyramid's link carries its scope, so the points counted there are the ones shown.
  const [scope, setScope] = useState<Scope>(initialScope);
  const [horizon, setHorizon] = useState(24);
  const [allAssets, setAllAssets] = useState(false);
  const query = useQuery(goalAnalysisQuery(scope, horizon, allAssets));
  const data = query.data;
  const none = data && data.timeline.length === 0 && data.forward.bands.length === 0;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{a.title}</h1>
          <p className="max-w-2xl text-sm text-muted">{a.intro}</p>
        </div>
        <ScopeSelect
          value={scope}
          onChange={setScope}
          labelClassName={labelClass}
          fieldClassName={fieldClass}
        />
      </div>
      {query.isError && <ErrorAlert message={a.loadFailed} />}
      {query.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {data && (
        <>
          <p className="text-sm text-muted">
            {data.reference ? a.reference(monthLabel(data.reference)) : a.noReference}
          </p>
          <Points data={data} scope={scope} />
          {none ? (
            <p className="text-sm">{a.empty}</p>
          ) : (
            <>
              <Forward
                data={data}
                horizon={horizon}
                onHorizon={setHorizon}
                scoped={scope !== "household"}
              />
              <Timeline data={data} />
              <RiskChart data={data} />
              <GoalChances data={data} />
              <MoneySankey sankey={data.sankey} allAssets={allAssets} onAllAssets={setAllAssets} />
              <StatusGrid data={data} />
            </>
          )}
        </>
      )}
    </div>
  );
}
