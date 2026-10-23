import { keepPreviousData, useQuery, useSuspenseQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { listGoals, type Scope } from "../api/generated";
import { meQuery } from "../auth/session";
import { ScopeSelect } from "../components/ScopeSelect";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurWhole } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";
import { goalAnalysisQuery } from "./AnalysisPage";
import { EffortPlan } from "./EffortPlan";
import { GoalCard } from "./GoalCard";
import { GoalForm } from "./GoalForm";
import { GoalSettings } from "./GoalSettings";
import { Pyramid } from "./Pyramid";
import { GOALS_KEY, TIERS, tierColour } from "./shared";

const labelClass = "flex flex-col gap-1 text-sm font-medium";
const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

export function goalsQuery(scope: Scope) {
  return {
    queryKey: [...GOALS_KEY, "list", scope],
    queryFn: async () => (await listGoals({ query: { scope }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  };
}

/** The Goals space (F-GOAL-7): the pyramid, the month's effort and every goal by tier. */
export function GoalsPage() {
  const { t } = useI18n();
  const g = t.goals;
  const { data: user } = useSuspenseQuery(meQuery);
  const [scope, setScope] = useState<Scope>("household");
  const [panel, setPanel] = useState<"new" | "settings" | null>(null);
  // Archived and cancelled goals stay out of sight until asked for (F-GOAL-8).
  const [showClosed, setShowClosed] = useState(false);
  const query = useQuery(goalsQuery(scope));
  // The points to look at are counted here and read on the Analysis tab (F-ANA-8).
  const analysis = useQuery(goalAnalysisQuery(scope, 24));
  const points = analysis.data
    ? analysis.data.points.shown.length + analysis.data.points.more.length
    : 0;
  const data = query.data;
  const precaution = data?.goals.filter((goal) => goal.precaution && goal.status === "fill_first");
  const missing = precaution?.reduce((sum, goal) => sum + Number(goal.remaining), 0) ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{g.title}</h1>
          <p className="max-w-2xl text-sm text-muted">{g.intro}</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <ScopeSelect
            value={scope}
            onChange={setScope}
            labelClassName={labelClass}
            fieldClassName={fieldClass}
          />
          <Button variant="ghost" onClick={() => setPanel("settings")}>
            {g.settings}
          </Button>
          <Button onClick={() => setPanel("new")}>{g.newGoal}</Button>
        </div>
      </div>
      {panel === "new" && <GoalForm onDone={() => setPanel(null)} />}
      {panel === "settings" && (
        <GoalSettings isOwner={user.role === "owner"} onDone={() => setPanel(null)} />
      )}
      {points > 0 && (
        <p className="text-sm">
          <Link
            to="/goals/analysis"
            search={{ scope }}
            className="font-medium text-accent hover:underline"
          >
            {t.goalAnalysis.pointsLink(points)} <span aria-hidden="true">→</span>
          </Link>
        </p>
      )}
      {query.isError && <ErrorAlert message={g.loadFailed} />}
      {query.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {data && missing > 0 && (
        <div
          role="status"
          className="flex gap-3 rounded-lg border border-l-4 border-border bg-surface p-4 text-sm"
          style={{ borderLeftColor: "var(--color-goal-priority)" }}
        >
          <span aria-hidden="true" className="text-lg leading-none">
            ⚠
          </span>
          <p>
            <strong>{g.precautionMissing(formatEurWhole(String(missing)))}</strong>{" "}
            {g.precautionFirst}
          </p>
        </div>
      )}
      {data && data.goals.length === 0 && data.closed.length === 0 && (
        <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4 text-sm">
          <p>{g.empty}</p>
          <p className="text-muted">
            {g.emptyWealth}{" "}
            <Link to="/wealth" className="text-accent hover:underline">
              {g.openWealth}
            </Link>
          </p>
        </div>
      )}
      {data && data.goals.length > 0 && (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <Pyramid data={data} />
            <EffortPlan data={data} />
          </div>
          {TIERS.map((tier) => {
            const goals = data.goals.filter((goal) => goal.tier === tier);
            if (goals.length === 0) return null;
            const p = data.pyramid.find((x) => x.tier === tier);
            return (
              <section key={tier} aria-labelledby={`tier-${tier}`} className="flex flex-col gap-3">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <h2 id={`tier-${tier}`} className="text-xl font-bold">
                    {g.tiers[tier]}
                  </h2>
                  <span className="text-sm text-muted">{g.horizons[tier]}</span>
                  <div
                    aria-hidden="true"
                    className="h-1.5 min-w-24 flex-1 self-center overflow-hidden rounded-full bg-budget-on-bg"
                  >
                    <div
                      className="h-full"
                      style={{
                        width: `${Math.min(100, 100 * Number(p?.progress ?? 0))}%`,
                        background: tierColour(tier),
                      }}
                    />
                  </div>
                  <span className="text-sm tabular">
                    {g.ofTarget(formatEurWhole(p?.value ?? "0"), formatEurWhole(p?.target ?? "0"))}
                  </span>
                </div>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {goals.map((goal) => (
                    <GoalCard key={goal.id} goal={goal} plan={data.plan} month={data.month} />
                  ))}
                </div>
              </section>
            );
          })}
        </>
      )}
      {data && data.closed.length > 0 && (
        <div className="flex flex-col gap-3">
          <div>
            <Button
              variant="ghost"
              aria-expanded={showClosed}
              onClick={() => setShowClosed((shown) => !shown)}
            >
              {showClosed ? g.hideClosed : g.showClosed(data.closed.length)}
            </Button>
          </div>
          {showClosed && (
            <section
              aria-labelledby="closed-goals"
              className="rounded-lg border border-border bg-surface p-4 text-sm"
            >
              <h2 id="closed-goals" className="font-semibold">
                {g.closedGoals}
              </h2>
              <ul className="mt-3 flex flex-col gap-2">
                {data.closed.map((goal) => (
                  <li key={goal.id} className="flex flex-wrap justify-between gap-2">
                    <Link
                      to="/goals/$goalId"
                      params={{ goalId: goal.id }}
                      className="text-accent hover:underline"
                    >
                      {goal.name}
                    </Link>
                    <span className="text-muted">
                      {g.closedOn(
                        goal.closed_as ? g.closedAs[goal.closed_as] : "",
                        goal.closed_from ? monthLabel(shiftMonth(goal.closed_from, -1)) : "",
                      )}{" "}
                      · <span className="tabular">{formatEurWhole(goal.value)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
