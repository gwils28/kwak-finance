/**
 * Dashboard charts, in the emphasis form: the accent hue for spending (the subject), grey for
 * context (income, the budget pace). Colours are tokens checked with the dataviz validator.
 * Every chart has a table twin, so no value is reachable only by hovering.
 */
import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CategorySpending, DayPoint, MonthPoint } from "../api/generated";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { formatEurWhole, formatPercent } from "../lib/money";
import { daysInMonth, monthLabel, thisMonth } from "../lib/months";

const ACCENT = "var(--color-chart-accent)";
const CONTEXT = "var(--color-chart-context)";
const GRID = "var(--color-chart-grid)";
const MUTED = "var(--color-muted)";
const AXIS = { stroke: GRID, tick: { fill: MUTED, fontSize: 12 }, tickLine: false } as const;
const TOOLTIP = {
  contentStyle: {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    borderRadius: 6,
    color: "var(--color-fg)",
  },
  labelStyle: { color: "var(--color-fg)" },
  formatter: (value: unknown) => formatEurWhole(Number(value)),
};

/** Round, evenly spaced ticks from 0 past `max`, about four steps: 2 480 -> 0, 1 000…3 000. */
export function niceTicks(max: number): number[] {
  if (max <= 0) return [0, 100];
  const rough = max / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = ([1, 2, 2.5, 5, 10].find((s) => s * magnitude >= rough) ?? 10) * magnitude;
  const ticks = [];
  for (let tick = 0; tick < max + step; tick += step) ticks.push(tick);
  return ticks;
}

function axisTicks(values: number[]): { ticks: number[]; domain: [number, number] } {
  const ticks = niceTicks(Math.max(0, ...values));
  return { ticks, domain: [0, ticks.at(-1) ?? 100] };
}

/** Legend names in the text colour: the marker beside them carries the series colour. */
const legendText = (value: string) => <span style={{ color: "var(--color-fg)" }}>{value}</span>;

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div>
        <h2 className="text-lg font-bold">{title}</h2>
        {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function DataTable({ label, head, rows }: { label: string; head: string[]; rows: string[][] }) {
  const { t } = useI18n();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">{t.common.showData}</summary>
      <table aria-label={label} className="mt-2 w-full">
        <thead className="text-left text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={h} className={`py-1 font-medium ${i > 0 ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row[0]} className="border-t border-border">
              {row.map((cell, i) => (
                <td
                  key={`${row[0]}-${head[i]}`}
                  className={`tabular py-1 ${i > 0 ? "text-right" : ""}`}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Nominal categories: one hue for every bar, sorted by spending, value at the tip. */
export function SpendingByCategory({
  month,
  categories,
}: {
  month: string;
  categories: CategorySpending[];
}) {
  const { t } = useI18n();
  const data = categories.map((c) => ({ name: c.name, spent: Number(c.spent) }));
  const height = Math.max(120, data.length * 36 + 40);
  return (
    <Card title={t.dashboard.byCategory} subtitle={monthLabel(month)}>
      {data.length === 0 ? (
        <p className="text-sm text-muted">{t.dashboard.noCategorised}</p>
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 0, right: 72, bottom: 0, left: 0 }}
            >
              <CartesianGrid horizontal={false} stroke={GRID} />
              <XAxis
                type="number"
                {...AXIS}
                {...axisTicks(data.map((d) => d.spent))}
                tickFormatter={(v: number) => formatEurWhole(v)}
              />
              <YAxis type="category" dataKey="name" width={130} {...AXIS} axisLine={false} />
              <Tooltip {...TOOLTIP} cursor={{ fill: GRID, opacity: 0.4 }} />
              <Bar
                dataKey="spent"
                name={t.dashboard.spent}
                fill={ACCENT}
                barSize={20}
                radius={[0, 4, 4, 0]}
                isAnimationActive={false}
              >
                <LabelList
                  dataKey="spent"
                  position="right"
                  formatter={(v: unknown) => formatEurWhole(Number(v))}
                  style={{ fill: "var(--color-fg)", fontSize: 12 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <DataTable
        label={t.dashboard.byCategoryOf(monthLabel(month))}
        head={[t.dashboard.category, t.dashboard.spent, t.dashboard.share]}
        rows={categories.map((c) => [
          c.name,
          formatEurWhole(c.spent),
          c.share === null ? "" : formatPercent(c.share),
        ])}
      />
    </Card>
  );
}

/** Spending columns (accent) against the income line (grey), one euro axis. */
export function SpendingOverMonths({ monthly }: { monthly: MonthPoint[] }) {
  const { t } = useI18n();
  // Months before the first transaction are not months of zero: leave them out.
  const first = monthly.findIndex((m) => Number(m.spent) !== 0 || Number(m.income) !== 0);
  const shown = first === -1 ? monthly : monthly.slice(first);
  const data = shown.map((m) => ({
    month: monthLabel(m.month),
    spent: Number(m.spent),
    income: Number(m.income),
  }));
  return (
    <Card
      title={t.dashboard.overMonths}
      subtitle={
        shown.length === 12
          ? t.dashboard.last12
          : t.dashboard.since(monthLabel(shown[0]?.month ?? ""))
      }
    >
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="month" {...AXIS} interval="preserveStartEnd" />
            <YAxis
              {...AXIS}
              axisLine={false}
              width={72}
              {...axisTicks(data.flatMap((d) => [d.spent, d.income]))}
              tickFormatter={(v: number) => formatEurWhole(v)}
            />
            <Tooltip {...TOOLTIP} cursor={{ stroke: GRID }} />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={legendText} />
            <Bar
              dataKey="spent"
              name={t.dashboard.spent}
              fill={ACCENT}
              barSize={20}
              radius={[4, 4, 0, 0]}
              isAnimationActive={false}
            />
            <Line
              dataKey="income"
              name={t.dashboard.income}
              stroke={CONTEXT}
              strokeWidth={2}
              dot={{ r: 4, fill: CONTEXT, stroke: "var(--color-surface)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={t.dashboard.overMonthsTable}
        head={[t.dashboard.monthColumn, t.dashboard.spent, t.dashboard.income]}
        rows={monthly.map((m) => [
          monthLabel(m.month),
          formatEurWhole(m.spent),
          formatEurWhole(m.income),
        ])}
      />
    </Card>
  );
}

/** Cumulative spending (accent line and wash) against the budget pace (grey, 0 -> target). */
export function SpendingPace({
  month,
  cumulative,
  target,
}: {
  month: string;
  cumulative: DayPoint[];
  target: string | null;
}) {
  const { t } = useI18n();
  const days = daysInMonth(month);
  const pace = (index: number) => (target === null ? null : (Number(target) * (index + 1)) / days);
  // The current month stops at today: the days to come have no spending yet, not zero.
  const today = month === thisMonth() ? new Date().getDate() : days;
  const data = cumulative.map((p, i) => ({
    day: Number(p.day.slice(8)),
    spent: i < today ? Number(p.spent) : null,
    pace: pace(i),
  }));
  return (
    <Card
      title={t.dashboard.pace}
      subtitle={
        target === null ? t.dashboard.noTarget : t.dashboard.againstBudget(formatEurWhole(target))
      }
    >
      <div style={{ height: 260 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="day" {...AXIS} interval={6} />
            <YAxis
              {...AXIS}
              axisLine={false}
              width={72}
              {...axisTicks(data.flatMap((d) => [d.spent ?? 0, d.pace ?? 0]))}
              tickFormatter={(v: number) => formatEurWhole(v)}
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(d: unknown) => t.dashboard.dayNumber(String(d))}
              cursor={{ stroke: GRID }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={legendText} />
            <Area
              dataKey="spent"
              name={t.dashboard.spentSoFar}
              stroke={ACCENT}
              strokeWidth={2}
              fill={ACCENT}
              fillOpacity={0.1}
              isAnimationActive={false}
            />
            {target !== null && (
              <Line
                dataKey="pace"
                name={t.dashboard.budgetPace}
                stroke={CONTEXT}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={t.dashboard.paceTable}
        head={
          target === null
            ? [t.dashboard.day, t.dashboard.spentSoFar]
            : [t.dashboard.day, t.dashboard.spentSoFar, t.dashboard.budgetPace]
        }
        rows={cumulative.map((p, i) => {
          const row = [formatDate(p.day), formatEurWhole(p.spent)];
          const expected = pace(i);
          return expected === null ? row : [...row, formatEurWhole(expected)];
        })}
      />
    </Card>
  );
}
