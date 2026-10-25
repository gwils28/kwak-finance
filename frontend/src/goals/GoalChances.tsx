import type { GoalAnalysisOut, GoalChanceOut } from "../api/generated";
import { Card } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";
import { tierColour } from "./shared";

/** A chance to the whole percent, never 0 nor 100 (F-SIM-5). */
function useChance() {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  return (share: string) => {
    const n = Number(share);
    if (n < 0.01) return a.chanceLow;
    if (n > 0.99) return a.chanceHigh;
    return formatPercent(share);
  };
}

function Outcome({
  certain,
  chance,
  short,
}: {
  certain: boolean;
  chance: string | null;
  short: string | null;
}) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const said = useChance();
  if (chance === null) return <>—</>;
  if (certain) {
    return (
      <>{short && Number(short) > 0 ? a.chanceShort(formatEurWhole(short)) : a.chanceReached}</>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className="inline-block h-2 w-16 overflow-hidden rounded-full bg-border"
      >
        <span
          className="block h-full bg-accent"
          style={{ width: `${Math.round(Number(chance) * 100)}%` }}
        />
      </span>
      {said(chance)}
    </span>
  );
}

/**
 * The chance of reaching each goal (F-ANA-7), at the plan's allocation and at the required
 * effort; a goal on lines without volatility is reached or short by an amount. The table is
 * the view (F-ANA-9).
 */
export function GoalChances({ data }: { data: GoalAnalysisOut }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const rows: GoalChanceOut[] = data.chances;
  if (rows.length === 0 && data.precaution_months === null) return null;
  return (
    <Card title={a.chances} subtitle={a.chancesHelp}>
      {data.precaution_months !== null && (
        <p className="text-sm">{a.precautionMonths(data.precaution_months)}</p>
      )}
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table aria-label={a.chancesTable} className="w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className="py-1 pr-3 font-medium">{a.goal}</th>
                <th className="py-1 pr-3 font-medium">{a.chanceDeadline}</th>
                <th className="py-1 pr-3 font-medium">{a.chanceAtPlan}</th>
                <th className="py-1 pr-3 font-medium">{a.chanceAtRequired}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.goal_id} className="border-t border-border align-top">
                  <th scope="row" className="whitespace-nowrap py-2 pr-3 text-left font-normal">
                    <span
                      aria-hidden="true"
                      className="mr-2 inline-block size-2.5 rounded-full align-middle"
                      style={{ background: tierColour(row.tier) }}
                    />
                    {row.name}
                  </th>
                  <td className="whitespace-nowrap py-2 pr-3">{monthLabel(row.deadline)}</td>
                  <td className="py-2 pr-3">
                    <Outcome
                      certain={row.certain}
                      chance={row.chance_planned}
                      short={row.short_planned}
                    />
                    <span className="block text-muted">
                      {a.aMonth(formatEurWhole(row.planned))}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <Outcome
                      certain={row.certain}
                      chance={row.chance_required}
                      short={row.short_required}
                    />
                    {row.required !== null && (
                      <span className="block text-muted">
                        {a.aMonth(formatEurWhole(row.required))}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-sm text-muted">{a.chancesNote}</p>
    </Card>
  );
}
