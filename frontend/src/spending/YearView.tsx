import { useQuery } from "@tanstack/react-query";
import type { SpendingYearLineOut } from "../api/generated";
import { ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent, formatPercentSigned } from "../lib/money";
import { monthLabel, thisMonth } from "../lib/months";
import { LOOK } from "./BudgetPage";
import { yearQuery } from "./queries";

/** The year (F-BUD-10): targets to date and for the year against the spending to date. */
export function YearView({ year }: { year: number }) {
  const { t } = useI18n();
  const b = t.spendingBudget;
  const y = b.yearView;
  const query = useQuery(yearQuery(year));

  if (query.isError) return <ErrorAlert message={t.errors.generic} />;
  if (!query.data) return <p>{t.common.loading}</p>;
  const data = query.data;
  const lastMonth = data.months.at(-1);

  const head = (savings: boolean) => (
    <tr className="text-left text-muted">
      <th scope="col" className="px-3 py-2 font-medium">
        {b.category}
      </th>
      <th scope="col" className="px-2 py-2 text-right font-medium">
        {y.toDate}
      </th>
      <th scope="col" className="px-2 py-2 text-right font-medium">
        {savings ? y.savedToDate : y.spentToDate}
      </th>
      <th scope="col" className="px-2 py-2 text-right font-medium">
        {y.gap}
      </th>
      <th scope="col" className="px-2 py-2 font-medium">
        {y.status}
      </th>
      <th scope="col" className="px-2 py-2 text-right font-medium">
        {savings ? y.savingsMonthsCount : y.monthsCount}
      </th>
      <th scope="col" className="px-2 py-2 text-right font-medium">
        {y.fullYear}
      </th>
    </tr>
  );

  const line = (l: SpendingYearLineOut) => (
    <tr key={l.category_id} className="border-t border-border">
      <th scope="row" className="px-3 py-2 text-left font-medium">
        {l.name}
      </th>
      <td className="tabular px-2 py-2 text-right">
        {l.target_to_date === null ? b.noTarget : formatEurWhole(l.target_to_date)}
      </td>
      <td className="tabular px-2 py-2 text-right">{formatEurWhole(l.spent_to_date)}</td>
      <td className="tabular px-2 py-2 text-right">
        {l.gap === null ? "" : formatEurSigned(l.gap)}
        {l.gap_ratio !== null && ` · ${formatPercentSigned(l.gap_ratio)}`}
      </td>
      <td className="px-2 py-1">
        <span className={`rounded px-2 py-1 text-xs ${LOOK[l.status]}`}>{b.status[l.status]}</span>
      </td>
      <td className="tabular px-2 py-2 text-right">{y.counts(l.above, l.on, l.below)}</td>
      <td className="tabular px-2 py-2 text-right">
        {l.target_full === null ? b.noTarget : formatEurWhole(l.target_full)}
      </td>
    </tr>
  );

  const totals = data.totals;
  const tiles: [string, string][] = [
    [b.income, formatEurWhole(totals.income)],
    [b.spent, formatEurWhole(totals.spent)],
    [b.saved, formatEurWhole(totals.saved)],
    [b.rest, formatEurSigned(totals.rest)],
    [y.savingsRate, totals.savings_rate === null ? "—" : formatPercent(totals.savings_rate)],
  ];

  return (
    <div className="flex flex-col gap-6">
      <section aria-label={y.totals} className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {tiles.map(([label, value]) => (
          <div
            key={label}
            className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
          >
            <span className="text-sm text-muted">{label}</span>
            <span className="tabular text-lg font-semibold">{value}</span>
          </div>
        ))}
      </section>
      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full min-w-[48rem] text-sm" aria-label={y.caption(year)}>
          <thead>{head(false)}</thead>
          <tbody>
            <tr>
              <th
                colSpan={7}
                className="px-3 pt-3 pb-1 text-left text-xs font-semibold text-muted uppercase"
              >
                {b.expenses}
              </th>
            </tr>
            {data.expenses.map(line)}
          </tbody>
          {data.savings.length > 0 && (
            <tbody>
              <tr>
                <th
                  colSpan={7}
                  className="px-3 pt-4 pb-1 text-left text-xs font-semibold text-muted uppercase"
                >
                  {b.savings}
                </th>
              </tr>
              {head(true)}
              {data.savings.map(line)}
            </tbody>
          )}
          {data.income.length > 0 && (
            <tbody>
              <tr>
                <th
                  colSpan={7}
                  className="px-3 pt-4 pb-1 text-left text-xs font-semibold text-muted uppercase"
                >
                  {b.income}
                </th>
              </tr>
              <tr className="text-left text-muted">
                <th scope="col" className="px-3 py-2 font-medium">
                  {b.category}
                </th>
                <td />
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  {y.receivedToDate}
                </th>
                <td colSpan={4} />
              </tr>
              {/* Income categories have no target: what they received, nothing to judge. */}
              {data.income.map((l) => (
                <tr key={l.category_id} className="border-t border-border">
                  <th scope="row" className="px-3 py-2 text-left font-medium">
                    {l.name}
                  </th>
                  <td />
                  <td className="tabular px-2 py-2 text-right">
                    {formatEurWhole(l.spent_to_date)}
                  </td>
                  <td colSpan={4} />
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
      {lastMonth && year === Number(thisMonth().slice(0, 4)) && (
        <p className="text-xs text-muted">{y.note(monthLabel(lastMonth))}</p>
      )}
    </div>
  );
}
