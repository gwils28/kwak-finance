/**
 * Dashboard charts, in the emphasis form: the accent hue for spending (the subject), grey for
 * context (income, the budget pace). Colours are tokens checked with the dataviz validator.
 * Every chart has a table twin, so no value is reachable only by hovering.
 */
import { type ReactNode, useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import { formatEurWhole } from "../lib/money";
import { daysInMonth, monthLabel, thisMonth } from "../lib/months";

export const ACCENT = "var(--color-chart-accent)";
export const CONTEXT = "var(--color-chart-context)";
export const GRID = "var(--color-chart-grid)";
const MUTED = "var(--color-muted)";
export const AXIS = { stroke: GRID, tick: { fill: MUTED, fontSize: 12 }, tickLine: false } as const;
export const TOOLTIP = {
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

export function axisTicks(values: number[]): { ticks: number[]; domain: [number, number] } {
  const ticks = niceTicks(Math.max(0, ...values));
  return { ticks, domain: [0, ticks.at(-1) ?? 100] };
}

/** Legend names in the text colour: the marker beside them carries the series colour. */
export const legendText = (value: string) => (
  <span style={{ color: "var(--color-fg)" }}>{value}</span>
);

/** A chart's frame: a region named by its title. `aside` holds controls next to the title. */
export function Card({
  title,
  subtitle,
  aside,
  children,
}: {
  title: string;
  subtitle?: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id={id} className="text-lg font-bold">
            {title}
          </h2>
          {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

export function DataTable({
  label,
  head,
  rows,
}: {
  label: string;
  head: string[];
  rows: string[][];
}) {
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

/** Cumulative spending (accent line and wash) against the budget pace (grey, 0 -> target). */
export function SpendingPace({
  month,
  cumulative,
  target,
}: {
  month: string;
  /** Spent from the first of the month to each day. */
  cumulative: { day: string; spent: string }[];
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
      title={month === thisMonth() ? t.dashboard.pace : t.dashboard.paceOf(monthLabel(month))}
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
        // The days to come have no spending yet: the table stops at today, as the line does.
        rows={cumulative.slice(0, today).map((p, i) => {
          const row = [formatDate(p.day), formatEurWhole(p.spent)];
          const expected = pace(i);
          return expected === null ? row : [...row, formatEurWhole(expected)];
        })}
      />
    </Card>
  );
}
