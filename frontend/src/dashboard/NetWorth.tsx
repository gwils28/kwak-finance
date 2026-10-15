import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type Scope, wealthMatrix } from "../api/generated";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercentSigned } from "../lib/money";

/**
 * Net worth at the end of the overview's month and its change over that month (F-WLT-7), in
 * the overview's scope. Nothing until a wealth line exists, and nothing if it cannot load:
 * the wealth page says why.
 */
export function NetWorth({ month, scope }: { month: string; scope: Scope }) {
  const { t } = useI18n();
  const query = useQuery({
    queryKey: ["wealth", "matrix", scope, { start: month, end: month }],
    queryFn: async () =>
      (await wealthMatrix({ query: { start: month, end: month, scope }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  const data = query.data;
  if (!data || data.categories.every((c) => c.lines.length === 0)) return null;
  const net = data.net[0] ?? "0";
  const change = data.change[0] ?? null;
  const ratio = data.change_ratio[0] ?? null;
  return (
    <section
      aria-label={t.dashboard.netWorth}
      className="flex flex-wrap items-end justify-between gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-col gap-1">
        <h2 className="text-sm text-muted">{t.dashboard.netWorth}</h2>
        <p className="text-3xl font-semibold">{formatEurWhole(net)}</p>
        <p className="text-xs">
          {change === null
            ? t.wealth.nothingBefore
            : t.wealth.versusLastMonth(
                ratio === null
                  ? formatEurSigned(change)
                  : `${formatEurSigned(change)} · ${formatPercentSigned(ratio)}`,
              )}
        </p>
      </div>
      <Link to="/wealth" className="text-sm text-accent hover:underline">
        {t.dashboard.openWealth}
      </Link>
    </section>
  );
}
