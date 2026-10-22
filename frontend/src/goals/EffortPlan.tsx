import type { GoalOut, GoalsOut } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole } from "../lib/money";
import { tierColour } from "./shared";

/** What a goal asks of this month: what is missing for the emergency fund and pleasure goals,
 * its required effort else. */
function need(goal: GoalOut): string | null {
  if (goal.precaution || goal.pleasure) return goal.remaining;
  return goal.required;
}

/** The month's effort plan: what you can save, shared out with the emergency fund first. */
export function EffortPlan({ data }: { data: GoalsOut }) {
  const { t } = useI18n();
  const g = t.goals;
  const plan = data.plan;
  const capacity = Number(plan.capacity);
  const rows = data.goals.filter((goal) => goal.effort !== null);
  const others = rows.filter((goal) => !goal.precaution && !goal.pleasure);
  const given = others.reduce((sum, goal) => sum + Number(goal.effort), 0);
  const needed = others.reduce((sum, goal) => sum + Number(goal.required ?? 0), 0);
  return (
    <section
      aria-labelledby="goals-effort"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div>
        <h2 id="goals-effort" className="text-lg font-bold">
          {g.effort}
        </h2>
        <p className="text-sm text-muted">
          {plan.capacity_set ? g.capacitySet : g.capacityComputed}
        </p>
      </div>
      <p className="text-3xl font-semibold tabular">{g.perMonth(formatEurWhole(plan.capacity))}</p>
      {rows.length === 0 ? (
        <p className="text-sm">{g.nothingToShare}</p>
      ) : (
        <>
          {capacity > 0 && (
            <div aria-hidden="true" className="flex h-6 gap-0.5 overflow-hidden rounded-md">
              {rows
                .filter((goal) => Number(goal.effort) > 0)
                .map((goal) => (
                  <div
                    key={goal.id}
                    title={`${goal.name}: ${formatEurWhole(goal.effort ?? "0")}`}
                    style={{
                      width: `${(100 * Number(goal.effort)) / capacity}%`,
                      background: tierColour(goal.tier),
                    }}
                  />
                ))}
              {Number(plan.unallocated) > 0 && (
                <div
                  className="flex-1 bg-budget-on-bg"
                  title={g.unallocated(formatEurWhole(plan.unallocated))}
                />
              )}
            </div>
          )}
          <table aria-label={g.effortTable} className="w-full text-sm">
            <thead className="sr-only">
              <tr>
                <th scope="col">{g.goal}</th>
                <th scope="col">{g.need}</th>
                <th scope="col">{g.given}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((goal) => {
                const amount = need(goal);
                return (
                  <tr key={goal.id}>
                    <th scope="row" className="py-1.5 text-left font-normal">
                      <span className="flex items-center gap-2">
                        <span
                          aria-hidden="true"
                          className="h-3 w-3 shrink-0 rounded-sm"
                          style={{ background: tierColour(goal.tier) }}
                        />
                        <span>
                          {goal.name}
                          {goal.precaution && plan.months_to_fill !== null && (
                            <span className="text-muted"> · {g.filledIn(plan.months_to_fill)}</span>
                          )}
                        </span>
                      </span>
                    </th>
                    <td className="px-2 py-1.5 text-right text-muted tabular whitespace-nowrap">
                      {amount === null
                        ? ""
                        : goal.precaution || goal.pleasure
                          ? g.missing(formatEurWhole(amount))
                          : g.required(formatEurWhole(amount))}
                    </td>
                    <td className="py-1.5 text-right font-semibold tabular whitespace-nowrap">
                      {formatEurWhole(goal.effort ?? "0")}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="text-sm text-muted">
            {Number(plan.shortfall) > 0
              ? g.shortfall(
                  formatEurWhole(String(given)),
                  formatEurWhole(String(needed)),
                  formatEurWhole(plan.shortfall),
                )
              : g.allServed}
            {Number(plan.unallocated) >= 1 && ` ${g.unallocated(formatEurWhole(plan.unallocated))}`}
          </p>
        </>
      )}
    </section>
  );
}
