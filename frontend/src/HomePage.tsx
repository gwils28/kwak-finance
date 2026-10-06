import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type ReactNode, useId, useState } from "react";
import { dashboard as fetchDashboard, type Kpis, type Scope } from "./api/generated";
import { ErrorAlert } from "./components/ui";
import { SpendingByCategory, SpendingOverMonths, SpendingPace } from "./dashboard/charts";
import { formatEurSigned, formatEurWhole, formatPercent, formatPercentSigned } from "./lib/money";
import { monthBounds, monthLabel, thisMonth } from "./lib/months";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";

export function HomePage() {
  const ids = { month: useId(), scope: useId() };
  const [month, setMonth] = useState(thisMonth());
  const [scope, setScope] = useState<Scope>("household");
  const query = useQuery({
    queryKey: ["dashboard", { month, scope }],
    queryFn: async () =>
      (await fetchDashboard({ query: { month, scope }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  const data = query.data;
  const empty = data?.monthly.every((m) => Number(m.spent) === 0 && Number(m.income) === 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-3xl font-black tracking-tight">Overview</h1>
        <div className="flex flex-wrap gap-3">
          <label htmlFor={ids.month} className="flex flex-col gap-1 text-sm font-medium">
            Month
            <input
              id={ids.month}
              type="month"
              className={fieldClass}
              value={month}
              max={thisMonth()}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
          <label htmlFor={ids.scope} className="flex flex-col gap-1 text-sm font-medium">
            Accounts
            <select
              id={ids.scope}
              className={fieldClass}
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
            >
              <option value="household">Household</option>
              <option value="mine">Only mine</option>
            </select>
          </label>
        </div>
      </div>
      {query.isError && <ErrorAlert message="Could not load the overview." />}
      {query.isPending && <p className="text-sm text-muted">Loading…</p>}
      {data && empty && (
        <section className="rounded-lg border border-border bg-surface p-6">
          <p>No transactions yet: import a bank statement to see your figures.</p>
          <Link to="/accounts" className="mt-3 inline-block text-accent hover:underline">
            Go to Accounts
          </Link>
        </section>
      )}
      {data && !empty && (
        <div className={`flex flex-col gap-6 ${query.isFetching ? "opacity-60" : ""}`}>
          <KpiRow kpis={data.kpis} month={data.month} toCategorise={data.to_categorise} />
          <div className="grid gap-6 lg:grid-cols-2">
            <SpendingByCategory
              month={data.month}
              categories={data.monthly.at(-1)?.by_category ?? []}
            />
            <SpendingPace
              month={data.month}
              cumulative={data.cumulative}
              target={data.budget_target}
            />
          </div>
          <SpendingOverMonths monthly={data.monthly} />
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <section
      aria-label={label}
      className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="text-sm text-muted">{label}</h2>
      <p className="text-2xl font-semibold">{value}</p>
      {children && <div className="text-xs">{children}</div>}
    </section>
  );
}

/** Spending going up is bad: an arrow and words carry it, the colour only reinforces. */
function SpendingChange({ ratio, against }: { ratio: string | null; against: string }) {
  if (ratio === null) return null;
  const up = Number(ratio) > 0;
  return (
    <p className={up ? "text-negative" : "text-positive"}>
      <span aria-hidden="true">{up ? "▲" : "▼"} </span>
      {formatPercentSigned(ratio)} vs {against}
    </p>
  );
}

function KpiRow({
  kpis,
  month,
  toCategorise,
}: {
  kpis: Kpis;
  month: string;
  toCategorise: { count: number; spent: string };
}) {
  const noComparison =
    kpis.spent_change_vs_previous === null && kpis.spent_change_vs_average === null;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Tile label="Spent" value={formatEurWhole(kpis.spent)}>
        {noComparison ? (
          <p className="text-muted">Nothing to compare with yet</p>
        ) : (
          <>
            <SpendingChange ratio={kpis.spent_change_vs_previous} against="last month" />
            <SpendingChange ratio={kpis.spent_change_vs_average} against="12-month average" />
          </>
        )}
      </Tile>
      <Tile label="Income" value={formatEurWhole(kpis.income)} />
      <Tile label="Net" value={formatEurSigned(kpis.net)}>
        <p className="text-muted">Income minus spending, transfers excluded</p>
      </Tile>
      <Tile
        label="Savings rate"
        value={kpis.savings_rate === null ? "—" : formatPercent(kpis.savings_rate)}
      >
        <p className="text-muted">
          {kpis.savings_rate === null ? "No income this month" : "Share of income kept"}
        </p>
      </Tile>
      <Tile label="To categorise" value={String(toCategorise.count)}>
        {toCategorise.count > 0 ? (
          <Link
            to="/transactions"
            search={{ category: "none", ...monthBounds(month) }}
            className="text-accent hover:underline"
          >
            Categorise them ({formatEurWhole(toCategorise.spent)} in {monthLabel(month)})
          </Link>
        ) : (
          <p className="text-muted">All categorised</p>
        )}
      </Tile>
    </div>
  );
}
