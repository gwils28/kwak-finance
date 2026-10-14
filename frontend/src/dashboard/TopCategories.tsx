import { Link } from "@tanstack/react-router";
import type { CategorySpending } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";
import { Card } from "./charts";

/** The month's five largest top-level categories; the rest of the analysis is in its report. */
export function TopCategories({
  month,
  categories,
}: {
  month: string;
  categories: CategorySpending[];
}) {
  const { t } = useI18n();
  return (
    <Card title={t.dashboard.topCategories} subtitle={monthLabel(month)}>
      {categories.length === 0 ? (
        <p className="text-sm text-muted">{t.dashboard.noCategorised}</p>
      ) : (
        <ol className="flex flex-col divide-y divide-border text-sm">
          {categories.map((c) => (
            <li key={c.category_id} className="flex items-baseline gap-3 py-2">
              <span className="flex-1 truncate" title={c.name}>
                {c.name}
              </span>
              <span className="tabular font-semibold">{formatEurWhole(c.spent)}</span>
              {c.share !== null && (
                <span className="tabular w-12 text-right text-muted">
                  {formatPercent(c.share)}
                  <span className="sr-only"> {t.dashboard.ofSpending}</span>
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
      <Link
        to="/reports"
        search={{ start: month, end: month }}
        className="self-start text-sm font-medium text-accent hover:underline"
      >
        {t.dashboard.seeReport}
      </Link>
    </Card>
  );
}
