import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { Scope } from "../api/generated";
import { goalsQuery } from "../goals/GoalsPage";
import { TIERS, tierColour } from "../goals/shared";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";

/**
 * The three tiers' progress and the emergency fund's warning (F-GOAL-9), in the overview's
 * scope. Nothing until a goal exists, and nothing if it cannot load: the goals page says why.
 */
export function GoalsTile({ scope }: { scope: Scope }) {
  const { t } = useI18n();
  const g = t.goals;
  const { data } = useQuery(goalsQuery(scope));
  if (!data || data.goals.length === 0) return null;
  const missing = data.goals
    .filter((goal) => goal.status === "fill_first")
    .reduce((sum, goal) => sum + Number(goal.remaining), 0);
  return (
    <section
      aria-label={g.tileTitle}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm text-muted">{g.tileTitle}</h2>
        <Link to="/goals" className="text-sm text-accent hover:underline">
          {g.openGoals}
        </Link>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {TIERS.map((tier) => {
          const p = data.pyramid.find((x) => x.tier === tier);
          return (
            <li key={tier} className="flex flex-col gap-1 text-sm">
              <span className="flex justify-between gap-2">
                <span>{g.tiers[tier]}</span>
                <span className="tabular font-semibold">
                  {p?.progress == null ? g.noGoalInTier : formatPercent(p.progress)}
                </span>
              </span>
              <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-budget-on-bg">
                <span
                  className="block h-full"
                  style={{
                    width: `${Math.min(100, 100 * Number(p?.progress ?? 0))}%`,
                    background: tierColour(tier),
                  }}
                />
              </span>
            </li>
          );
        })}
      </ul>
      {missing > 0 && (
        <p className="text-sm">
          <span aria-hidden="true">⚠ </span>
          {g.precautionMissing(formatEurWhole(String(missing)))}
        </p>
      )}
    </section>
  );
}
