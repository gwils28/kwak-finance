/**
 * Plan steering charts (F-DSH-6), in the dashboard's style: each has its table twin.
 */
import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BudgetStatus, CumulativeOut, ReviewRowOut } from "../api/generated";
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
import { formatDate } from "../lib/dates";
import { formatEurWhole, formatPercentSigned } from "../lib/money";

const STATUS_FILL: Record<BudgetStatus, string> = {
  under: "var(--color-chart-under)",
  on: "var(--color-chart-on)",
  over: "var(--color-chart-over)",
  none: "var(--color-chart-on)",
};

/** Symmetric round ticks around 0: 0.68 -> -0.75 … +0.75 by 0.25. */
function gapTicks(reach: number): number[] {
  const steps = [0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10];
  const step = steps.find((s) => s * 2 >= reach) ?? Math.ceil(reach / 2);
  return [-2, -1, 0, 1, 2].map((k) => k * step);
}

/** The projected gap in % per category with a target, coloured as its status. */
export function GapChart({ rows }: { rows: ReviewRowOut[] }) {
  const { t } = useI18n();
  const shown = rows.filter((r) => r.projected_gap_ratio !== null);
  // The value sits in the category label: a bar label would cross the axis when negative.
  const data = shown.map((r) => ({
    label: `${r.level === 1 ? "· " : ""}${r.name}  ${formatPercentSigned(r.projected_gap_ratio as string)}`,
    gap: Number(r.projected_gap_ratio),
    status: r.status,
  }));
  const ticks = gapTicks(Math.max(0.05, ...data.map((d) => Math.abs(d.gap))));
  const height = Math.max(120, data.length * 32 + 40);
  return (
    <Card title={t.review.gapChart} subtitle={t.review.gapChartHelp}>
      {data.length === 0 ? (
        <p className="text-sm text-muted">{t.review.gapNone}</p>
      ) : (
        <div style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={data}
              layout="vertical"
              margin={{ top: 0, right: 16, bottom: 0, left: 0 }}
            >
              <CartesianGrid horizontal={false} stroke={GRID} />
              <XAxis
                type="number"
                {...AXIS}
                ticks={ticks}
                domain={[ticks[0] as number, ticks.at(-1) as number]}
                tickFormatter={(v: number) => formatPercentSigned(v)}
              />
              <YAxis type="category" dataKey="label" width={190} {...AXIS} axisLine={false} />
              <ReferenceLine x={0} stroke={CONTEXT} />
              <Tooltip
                {...TOOLTIP}
                formatter={(v: unknown) => formatPercentSigned(Number(v))}
                cursor={{ fill: GRID, opacity: 0.4 }}
              />
              <Bar dataKey="gap" name={t.review.gap} barSize={18} isAnimationActive={false}>
                {data.map((d) => (
                  <Cell key={d.label} fill={STATUS_FILL[d.status]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <DataTable
        label={t.review.gapTable}
        head={[t.review.category, t.review.gap]}
        rows={shown.map((r) => [r.name, formatPercentSigned(r.projected_gap_ratio as string)])}
      />
    </Card>
  );
}

/** Cumulative spending (accent) against the envelope line (grey), day by day. */
export function CumulativeChart({ chart, aside }: { chart: CumulativeOut; aside: ReactNode }) {
  const { t } = useI18n();
  const data = chart.points.map((p) => ({
    day: p.day,
    spent: p.spent === null ? null : Number(p.spent),
    envelope: Number(p.envelope),
  }));
  const short = (day: string) => formatDate(day).replace(/\s\d{4}$/, "");
  return (
    <Card
      title={t.review.cumulative}
      subtitle={t.review.cumulativeHelp(formatEurWhole(chart.envelope))}
      aside={aside}
    >
      <div style={{ height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis
              dataKey="day"
              {...AXIS}
              interval="preserveStartEnd"
              minTickGap={40}
              tickFormatter={short}
            />
            <YAxis
              {...AXIS}
              axisLine={false}
              width={72}
              {...axisTicks(data.flatMap((d) => [d.spent ?? 0, d.envelope]))}
              tickFormatter={(v: number) => formatEurWhole(v)}
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(d: unknown) => formatDate(String(d))}
              cursor={{ stroke: GRID }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} formatter={legendText} />
            <Area
              dataKey="spent"
              name={t.review.spentSoFar}
              stroke={ACCENT}
              strokeWidth={2}
              fill={ACCENT}
              fillOpacity={0.1}
              isAnimationActive={false}
            />
            <Line
              dataKey="envelope"
              name={t.review.envelopeLine}
              stroke={CONTEXT}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={t.review.cumulativeTable}
        head={[t.review.day, t.review.spentSoFar, t.review.envelopeLine]}
        rows={chart.points
          .filter((p) => p.spent !== null)
          .map((p) => [
            formatDate(p.day),
            formatEurWhole(p.spent as string),
            formatEurWhole(p.envelope),
          ])}
      />
    </Card>
  );
}
