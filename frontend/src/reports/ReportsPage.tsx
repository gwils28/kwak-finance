import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  type ReportSection,
  type SpendingReportOut,
  type SpendingReportRowOut,
  spendingReport,
} from "../api/generated";
import { ErrorAlert } from "../components/ui";
import {
  ACCENT,
  AXIS,
  axisTicks,
  Card,
  CONTEXT,
  DataTable,
  GRID,
  legendText,
  TOOLTIP,
} from "../dashboard/charts";
import { useI18n } from "../i18n";
import {
  formatEurSigned,
  formatEurWhole,
  formatPercent,
  formatPercentSigned,
  fromCents,
  toCents,
} from "../lib/money";
import { isMonth, monthLabel, shiftMonth, thisMonth } from "../lib/months";
import { FlowsChart } from "../spending/FlowsChart";
import { SPENDING } from "../spending/queries";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
/** As the API: a report covers 10 years at most. */
const MAX_MONTHS = 120;

const PRESETS = [
  "thisMonth",
  "lastMonth",
  "thisQuarter",
  "thisYear",
  "lastYear",
  "last12",
] as const;
type Preset = (typeof PRESETS)[number] | "custom";
type Period = { start: string; end: string };

/** The months of a preset, around the current month. */
export function presetPeriod(preset: (typeof PRESETS)[number], today: string): Period {
  const year = today.slice(0, 4);
  const month = Number(today.slice(5, 7));
  const quarterStart = `${year}-${String(month - ((month - 1) % 3)).padStart(2, "0")}`;
  switch (preset) {
    case "thisMonth":
      return { start: today, end: today };
    case "lastMonth":
      return { start: shiftMonth(today, -1), end: shiftMonth(today, -1) };
    case "thisQuarter":
      return { start: quarterStart, end: shiftMonth(quarterStart, 2) };
    case "thisYear":
      return { start: `${year}-01`, end: `${year}-12` };
    case "lastYear":
      return { start: `${Number(year) - 1}-01`, end: `${Number(year) - 1}-12` };
    case "last12":
      return { start: shiftMonth(today, -11), end: today };
  }
}

function monthCount({ start, end }: Period): number {
  const index = (m: string) => Number(m.slice(0, 4)) * 12 + Number(m.slice(5, 7));
  return index(end) - index(start) + 1;
}

/** `initial`: the months to open on (a link from the overview), else this year. */
export function ReportsPage({ initial }: { initial?: Period }) {
  const { t } = useI18n();
  const ids = { preset: useId(), from: useId(), to: useId() };
  const [preset, setPreset] = useState<Preset>(initial ? "custom" : "thisYear");
  const [custom, setCustom] = useState<Period>(
    () => initial ?? presetPeriod("thisYear", thisMonth()),
  );
  const period = preset === "custom" ? custom : presetPeriod(preset, thisMonth());
  const started = !isMonth(period.start) || period.start <= thisMonth();
  const valid =
    started &&
    isMonth(period.start) &&
    isMonth(period.end) &&
    monthCount(period) >= 1 &&
    monthCount(period) <= MAX_MONTHS;

  const report = useQuery({
    queryKey: [SPENDING, "report", period],
    queryFn: async () => (await spendingReport({ query: period, throwOnError: true })).data,
    enabled: valid,
    placeholderData: keepPreviousData,
  });

  const choose = (next: Preset) => {
    // A custom period starts from the one on screen.
    if (next === "custom") setCustom(period);
    setPreset(next);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.reports.title}</h1>
          <p className="text-sm text-muted">{t.reports.intro}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label htmlFor={ids.preset} className={labelClass}>
            {t.reports.period}
            <select
              id={ids.preset}
              className={fieldClass}
              value={preset}
              onChange={(e) => choose(e.target.value as Preset)}
            >
              {[...PRESETS, "custom" as const].map((p) => (
                <option key={p} value={p}>
                  {t.reports.presets[p]}
                </option>
              ))}
            </select>
          </label>
          {preset === "custom" && (
            <>
              <label htmlFor={ids.from} className={labelClass}>
                {t.reports.from}
                <input
                  id={ids.from}
                  type="month"
                  className={fieldClass}
                  value={custom.start}
                  onChange={(e) => setCustom({ ...custom, start: e.target.value })}
                />
              </label>
              <label htmlFor={ids.to} className={labelClass}>
                {t.reports.to}
                <input
                  id={ids.to}
                  type="month"
                  className={fieldClass}
                  value={custom.end}
                  onChange={(e) => setCustom({ ...custom, end: e.target.value })}
                />
              </label>
            </>
          )}
        </div>
      </div>
      {!valid && <ErrorAlert message={started ? t.reports.badPeriod : t.reports.future} />}
      {valid && report.isError && <ErrorAlert message={t.reports.loadFailed} />}
      {valid && report.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {valid && report.data && <Report report={report.data} />}
    </div>
  );
}

function Report({ report }: { report: SpendingReportOut }) {
  const { t } = useI18n();
  const range = (start: string, end: string) => t.reports.range(monthLabel(start), monthLabel(end));
  return (
    <>
      <p className="text-sm text-muted">
        {report.to_date
          ? t.reports.soFar(range(report.start, report.end))
          : range(report.start, report.end)}{" "}
        ·{" "}
        {report.compared
          ? t.reports.comparedWith(range(report.previous_start, report.previous_end))
          : t.reports.notCompared(monthLabel(report.first_month ?? report.start))}
      </p>
      {report.first_month && report.first_month === report.start && (
        <p className="text-sm text-muted">{t.reports.firstMonth(monthLabel(report.first_month))}</p>
      )}
      <Summary report={report} />
      {report.rows.length === 0 ? (
        <p className="text-sm">{t.reports.nothing}</p>
      ) : (
        <>
          <CategoryTable report={report} />
          <SpendingChart report={report} />
        </>
      )}
      {report.months > 1 && <OverMonths report={report} />}
      <FlowsChart flows={report.flows} />
    </>
  );
}

/** `change` against the period before: left out for none shown, null for nothing before. */
function Figure({
  label,
  value,
  change,
  signed = false,
}: {
  label: string;
  value: string;
  change?: string | null;
  signed?: boolean;
}) {
  const { t } = useI18n();
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="tabular text-xl font-bold">
        {signed ? formatEurSigned(value) : formatEurWhole(value)}
      </dd>
      {change !== undefined && (
        <dd className="text-xs text-muted">
          {change === null ? t.reports.noPrevious : t.reports.versus(formatPercentSigned(change))}
        </dd>
      )}
    </div>
  );
}

function Summary({ report }: { report: SpendingReportOut }) {
  const { t } = useI18n();
  const id = useId();
  const now = report.totals;
  // Not compared: no change to show at all, rather than "nothing the period before".
  const change = (value: string | null) => (report.compared ? value : undefined);
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-4"
    >
      <h2 id={id} className="text-lg font-bold">
        {t.reports.summary}
      </h2>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <Figure
          label={t.reports.income}
          value={now.income}
          change={change(report.changes.income)}
        />
        <Figure label={t.reports.spent} value={now.spent} change={change(report.changes.spent)} />
        <Figure label={t.reports.saved} value={now.saved} change={change(report.changes.saved)} />
        <Figure
          label={t.reports.rest}
          value={now.rest}
          change={change(report.changes.rest)}
          signed
        />
        {now.savings_rate !== null && (
          <div className="flex flex-col gap-1">
            <dt className="text-sm text-muted">{t.reports.savingsRate}</dt>
            <dd className="tabular text-xl font-bold">{formatPercent(now.savings_rate)}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}

const SECTIONS: ReportSection[] = ["income", "spending", "savings"];

function CategoryTable({ report }: { report: SpendingReportOut }) {
  const { t } = useI18n();
  const cell = "whitespace-nowrap px-3 py-2 text-right tabular";
  const line = (r: SpendingReportRowOut) => (
    <tr key={`${r.section}-${r.category_id}`}>
      <th scope="row" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
        {r.name}
      </th>
      <td className={cell}>{formatEurWhole(r.amount)}</td>
      <td className={cell}>{formatEurWhole(r.monthly_average)}</td>
      <td className={cell}>{r.share === null ? "" : formatPercent(r.share)}</td>
      <td className={cell}>{report.compared ? formatEurWhole(r.previous) : ""}</td>
      <td className={cell}>{r.change === null ? "" : formatPercentSigned(r.change)}</td>
    </tr>
  );
  const headers = [
    t.reports.category,
    t.reports.total,
    t.reports.monthlyAverage,
    t.reports.share,
    t.reports.previous,
    t.reports.change,
  ];
  return (
    <Card title={t.reports.byCategory} subtitle={t.reports.byCategoryHelp}>
      <div className="overflow-x-auto">
        <table aria-label={t.reports.byCategory} className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              {headers.map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`whitespace-nowrap px-3 py-2 font-medium ${i > 0 ? "text-right" : ""}`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          {SECTIONS.map((section) => {
            const rows = report.rows.filter((r) => r.section === section);
            if (rows.length === 0) return null;
            const name = t.reports.sections[section];
            const total = report.sections.find((x) => x.section === section);
            if (!total) return null;
            return (
              <tbody key={section} aria-label={name} className="divide-y divide-border">
                <tr className="border-t-4 border-border">
                  <th
                    colSpan={headers.length}
                    scope="rowgroup"
                    className="px-3 pt-4 pb-2 text-left"
                  >
                    {name}
                  </th>
                </tr>
                {rows.map(line)}
                <tr className="border-t-2 border-border font-bold">
                  <th scope="row" className="whitespace-nowrap px-3 py-2 text-left">
                    {t.reports.sectionTotal(name)}
                  </th>
                  <td className={cell}>{formatEurWhole(total.amount)}</td>
                  <td className={cell}>{formatEurWhole(total.monthly_average)}</td>
                  <td className={cell}>{Number(total.amount) > 0 ? formatPercent(1) : ""}</td>
                  <td className={cell}>{report.compared ? formatEurWhole(total.previous) : ""}</td>
                  <td className={cell}>
                    {total.change === null ? "" : formatPercentSigned(total.change)}
                  </td>
                </tr>
              </tbody>
            );
          })}
        </table>
      </div>
    </Card>
  );
}

/** F-DSH-5: each expense category's spending over the period, one colour, the largest first. */
function SpendingChart({ report }: { report: SpendingReportOut }) {
  const { t } = useI18n();
  const rows = report.rows.filter((r) => r.section === "spending");
  if (rows.length === 0) return null;
  const data = rows.map((r) => ({ name: r.name, spent: Number(r.amount) }));
  return (
    <Card title={t.reports.spendingChart} subtitle={t.reports.spendingChartHelp}>
      <div style={{ height: Math.max(160, rows.length * 32 + 40) }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 16, bottom: 0, left: 0 }}
          >
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis
              type="number"
              {...AXIS}
              {...axisTicks(data.map((d) => d.spent))}
              tickFormatter={(v: number) => formatEurWhole(v)}
            />
            <YAxis type="category" dataKey="name" {...AXIS} width={120} />
            <Tooltip {...TOOLTIP} cursor={{ fill: GRID }} />
            <Bar
              dataKey="spent"
              name={t.reports.spent}
              fill={ACCENT}
              maxBarSize={20}
              radius={[0, 4, 4, 0]}
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={t.reports.spendingChartTable}
        head={[t.reports.category, t.reports.spent, t.reports.share]}
        rows={rows.map((r) => [
          r.name,
          formatEurWhole(r.amount),
          r.share === null ? "" : formatPercent(r.share),
        ])}
      />
    </Card>
  );
}

/** The period's six largest expense categories keep a colour each, in this order; the rest is grey. */
const SERIES = [1, 2, 3, 4, 5, 6].map((n) => `var(--color-spend-${n})`);
const OTHER = "var(--color-spend-other)";

/**
 * F-DSH-5: each month's spending stacked by category against the income line (one axis, in
 * euros). A category keeps its colour across the months; every series is in the legend and
 * has its column in the table.
 */
function OverMonths({ report }: { report: SpendingReportOut }) {
  const { t } = useI18n();
  // Only what spent this period: a category kept for the period before has nothing to draw.
  const ranked = report.rows.filter((r) => r.section === "spending" && toCents(r.amount) > 0);
  const named = ranked.slice(0, SERIES.length);
  const key = (id: string) => `c-${id}`;
  type Month = SpendingReportOut["monthly"][number];
  const amount = (m: Month, id: string) =>
    toCents(m.by_category.find((c) => c.category_id === id)?.spent ?? "0");
  // In whole cents, so an empty remainder is 0, never -0.
  const otherOf = (m: Month) =>
    named.reduce((rest, r) => rest - amount(m, r.category_id), toCents(m.spent));
  const hasOther = report.monthly.some((m) => otherOf(m) !== 0);
  const data = report.monthly.map((m) => {
    const point: Record<string, number | string> = {
      month: monthLabel(m.month),
      income: Number(m.income),
    };
    for (const r of named) point[key(r.category_id)] = amount(m, r.category_id) / 100;
    if (hasOther) point.other = otherOf(m) / 100;
    return point;
  });
  const values = report.monthly.flatMap((m) => [Number(m.spent), Number(m.income)]);
  return (
    <Card title={t.reports.overMonths} subtitle={t.reports.overMonthsHelp}>
      <div style={{ height: 300 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="month" {...AXIS} interval="preserveStartEnd" />
            <YAxis
              {...AXIS}
              axisLine={false}
              width={72}
              {...axisTicks(values)}
              tickFormatter={(v: number) => formatEurWhole(v)}
            />
            <Tooltip {...TOOLTIP} cursor={{ stroke: GRID }} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={legendText} />
            {named.map((r, i) => (
              <Bar
                key={r.category_id}
                dataKey={key(r.category_id)}
                name={r.name}
                stackId="spent"
                fill={SERIES[i]}
                // A thin surface gap between stacked segments.
                stroke="var(--color-surface)"
                strokeWidth={1}
                maxBarSize={24}
                isAnimationActive={false}
              />
            ))}
            {hasOther && (
              <Bar
                dataKey="other"
                name={t.reports.otherCategories}
                stackId="spent"
                fill={OTHER}
                stroke="var(--color-surface)"
                strokeWidth={1}
                maxBarSize={24}
                isAnimationActive={false}
              />
            )}
            <Line
              dataKey="income"
              name={t.reports.income}
              stroke={CONTEXT}
              strokeWidth={2}
              dot={{ r: 3, fill: CONTEXT, stroke: "var(--color-surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={t.reports.overMonthsTable}
        head={[
          t.reports.month,
          t.reports.income,
          ...named.map((r) => r.name),
          ...(hasOther ? [t.reports.otherCategories] : []),
          t.reports.spent,
          t.reports.saved,
          t.reports.rest,
        ]}
        rows={report.monthly.map((m) => [
          monthLabel(m.month),
          formatEurWhole(m.income),
          ...named.map((r) => formatEurWhole(fromCents(amount(m, r.category_id)))),
          ...(hasOther ? [formatEurWhole(fromCents(otherOf(m)))] : []),
          formatEurWhole(m.spent),
          formatEurWhole(m.saved),
          formatEurSigned(m.rest),
        ])}
      />
    </Card>
  );
}
