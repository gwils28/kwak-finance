/**
 * The projection's charts (F-SIM-5), interactive: hovering a month shows every series then.
 * Colours are the `projection-*` tokens, checked with the dataviz validator; every chart keeps
 * its legend and a table twin, so no value is reachable only by hovering.
 */

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
import type { CategoryOut, MonthOut, WhatIfOut } from "../api/generated";
import { AXIS, GRID, legendText } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurCompact, formatEurHundreds } from "../lib/money";
import { monthLabel } from "../lib/months";

export type View = "parts" | "fan";

const C = {
  today: "var(--color-projection-today)",
  contributed: "var(--color-projection-contributed)",
  repaid: "var(--color-projection-repaid)",
  gains: "var(--color-projection-gains)",
  losses: "var(--color-projection-losses)",
  median: "var(--color-projection-median)",
  inner: "var(--color-projection-band-inner)",
  outer: "var(--color-projection-band-outer)",
  amount: "var(--color-projection-amount)",
  fg: "var(--color-fg)",
};
export const WHAT_IF_COLOURS = [
  "var(--color-projection-whatif-1)",
  "var(--color-projection-whatif-2)",
];
const WHAT_IF_DASH = ["6 4", "2 3"];

type Row = {
  month: string;
  today: number;
  contributed: number;
  repaid: number;
  gains: number;
  losses: number;
  p50: number;
  inner: [number, number];
  outer: [number, number];
  p10: number;
  p25: number;
  p75: number;
  p90: number;
  [whatIf: `w${number}`]: number;
};

function rows(months: MonthOut[], whatIfs: (WhatIfOut | null)[]): Row[] {
  return months.map((m, t) => {
    const row: Row = {
      month: m.month,
      today: Number(m.today),
      contributed: Number(m.contributed),
      repaid: Number(m.repaid),
      gains: Math.max(0, Number(m.gains)),
      losses: Math.min(0, Number(m.gains)),
      p50: Number(m.p50),
      inner: [Number(m.p25), Number(m.p75)],
      outer: [Number(m.p10), Number(m.p90)],
      p10: Number(m.p10),
      p25: Number(m.p25),
      p75: Number(m.p75),
      p90: Number(m.p90),
    };
    whatIfs.forEach((w, k) => {
      if (w) row[`w${k}`] = Number(w.medians[t]);
    });
    return row;
  });
}

/** One tick a year at most, every 5 or 10 years over long horizons. */
function yearTicks(months: MonthOut[]): string[] {
  const years = (months.length - 1) / 12;
  const step = years > 20 ? 10 : years > 8 ? 5 : years > 3 ? 2 : 1;
  return months.filter((_, t) => t % (12 * step) === 0).map((m) => m.month);
}

type TipLine = { colour: string | null; name: string; value: number };

function Tip({ month, lines }: { month: string; lines: TipLine[] }) {
  return (
    <div className="min-w-48 rounded-md border border-border bg-surface p-2 text-xs shadow-md">
      <p className="mb-1 font-semibold">{monthLabel(month)}</p>
      {lines.map((line) => (
        <p key={line.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5">
            {line.colour && (
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: line.colour }}
              />
            )}
            {line.name}
          </span>
          <span className="tabular font-medium">{formatEurHundreds(line.value)}</span>
        </p>
      ))}
    </div>
  );
}

export function ProjectionChart({
  months,
  view,
  today,
  whatIfs,
  whatIfNames,
  amount,
}: {
  months: MonthOut[];
  view: View;
  /** Today's euros: the gains are after inflation. */
  today: boolean;
  whatIfs: (WhatIfOut | null)[];
  whatIfNames: string[];
  amount: number | null;
}) {
  const { t } = useI18n();
  const p = t.projection;
  const data = rows(months, whatIfs);
  const gainsName = today ? p.partGainsAfterInflation : p.partGains;
  const hasLosses = data.some((r) => r.losses < 0);

  const tooltip = ({ active, label }: { active?: boolean; label?: string | number }) => {
    const row = active ? data.find((r) => r.month === label) : undefined;
    if (!row) return null;
    const lines: TipLine[] =
      view === "parts"
        ? [
            { colour: null, name: p.median, value: row.p50 },
            { colour: C.gains, name: gainsName, value: row.gains + row.losses },
            { colour: C.repaid, name: p.partRepaid, value: row.repaid },
            { colour: C.contributed, name: p.partContributed, value: row.contributed },
            { colour: C.today, name: p.partToday, value: row.today },
          ]
        : [
            { colour: C.outer, name: p.p90, value: row.p90 },
            { colour: C.median, name: p.median, value: row.p50 },
            { colour: C.outer, name: p.p10, value: row.p10 },
          ];
    whatIfs.forEach((w, k) => {
      if (w) {
        lines.push({
          colour: WHAT_IF_COLOURS[k] ?? null,
          name: `${whatIfNames[k]} · ${p.median}`,
          value: row[`w${k}`] ?? 0,
        });
      }
    });
    return <Tip month={row.month} lines={lines} />;
  };

  return (
    <div className="h-72 sm:h-80" role="img" aria-label={p.chartLabel}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} stackOffset="sign" margin={{ top: 8, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="month"
            {...AXIS}
            ticks={yearTicks(months)}
            tickFormatter={(m: string) => m.slice(0, 4)}
          />
          <YAxis {...AXIS} width={64} tickFormatter={(v: number) => formatEurCompact(v)} />
          <Tooltip
            content={tooltip}
            cursor={{ stroke: "var(--color-muted)", strokeDasharray: "3 3" }}
          />
          <Legend
            formatter={legendText}
            wrapperStyle={{ fontSize: 12 }}
            itemSorter={null}
            iconType="circle"
          />
          {view === "parts" ? (
            <>
              <Area
                dataKey="today"
                name={p.partToday}
                stackId="parts"
                stroke="none"
                fill={C.today}
                fillOpacity={0.85}
                isAnimationActive={false}
              />
              <Area
                dataKey="contributed"
                name={p.partContributed}
                stackId="parts"
                stroke="none"
                fill={C.contributed}
                fillOpacity={0.85}
                isAnimationActive={false}
              />
              <Area
                dataKey="repaid"
                name={p.partRepaid}
                stackId="parts"
                stroke="none"
                fill={C.repaid}
                fillOpacity={0.85}
                isAnimationActive={false}
              />
              <Area
                dataKey="gains"
                name={gainsName}
                stackId="parts"
                stroke="none"
                fill={C.gains}
                fillOpacity={0.85}
                isAnimationActive={false}
              />
              {hasLosses && (
                <Area
                  dataKey="losses"
                  name={p.partLosses}
                  stackId="parts"
                  stroke="none"
                  fill={C.losses}
                  fillOpacity={0.85}
                  isAnimationActive={false}
                />
              )}
              <Line
                dataKey="p50"
                name={p.median}
                stroke={C.fg}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </>
          ) : (
            <>
              <Area
                dataKey="outer"
                name={p.band80}
                stroke="none"
                fill={C.outer}
                fillOpacity={1}
                isAnimationActive={false}
              />
              <Area
                dataKey="inner"
                name={p.band50}
                stroke="none"
                fill={C.inner}
                fillOpacity={1}
                isAnimationActive={false}
              />
              <Line
                dataKey="p50"
                name={p.median}
                stroke={C.median}
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
            </>
          )}
          {whatIfs.map((w, k) =>
            w ? (
              <Line
                key={whatIfNames[k]}
                dataKey={`w${k}`}
                name={whatIfNames[k]}
                stroke={WHAT_IF_COLOURS[k]}
                strokeDasharray={WHAT_IF_DASH[k]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ) : null,
          )}
          {amount !== null && amount > 0 && (
            <ReferenceLine
              y={amount}
              stroke={C.amount}
              strokeDasharray="4 3"
              label={{
                value: p.amountLine(formatEurHundreds(amount)),
                position: "insideTopLeft",
                fill: "var(--color-muted)",
                fontSize: 11,
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

const COLOUR = (key: string) => `var(--color-wealth-${key})`;

/** Each category's own median today (light) and at the horizon (full), debts below zero. */
export function CategoriesChart({
  categories,
  debts,
  shortfall,
}: {
  categories: CategoryOut[];
  debts: [number, number];
  shortfall: [number, number];
}) {
  const { t } = useI18n();
  const p = t.projection;
  const data = [
    ...categories.map((c) => ({
      name: c.name,
      colour: COLOUR(c.colour),
      today: Number(c.medians[0]),
      horizon: Number(c.medians.at(-1)),
    })),
    ...(debts[0] || debts[1]
      ? [{ name: p.debts, colour: COLOUR("debts"), today: -debts[0], horizon: -debts[1] }]
      : []),
    ...(shortfall[1]
      ? [{ name: p.shortfallName, colour: COLOUR("debts"), today: 0, horizon: -shortfall[1] }]
      : []),
  ];
  const height = Math.max(160, data.length * 44 + 40);
  return (
    <div className="flex flex-col gap-2">
      <div style={{ height }} role="img" aria-label={p.categoriesTitle}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }} barGap={2}>
            <CartesianGrid horizontal={false} stroke={GRID} />
            <XAxis type="number" {...AXIS} tickFormatter={(v: number) => formatEurCompact(v)} />
            <YAxis type="category" dataKey="name" {...AXIS} width={110} />
            <ReferenceLine x={0} stroke="var(--color-muted)" />
            <Tooltip
              cursor={{ fill: "var(--color-border)", fillOpacity: 0.3 }}
              content={({ active, payload }) => {
                const row = active ? payload?.[0]?.payload : undefined;
                if (!row) return null;
                return (
                  <div className="rounded-md border border-border bg-surface p-2 text-xs shadow-md">
                    <p className="mb-1 font-semibold">{row.name}</p>
                    <p className="flex justify-between gap-4">
                      {p.categoryToday}
                      <span className="tabular">{formatEurHundreds(row.today)}</span>
                    </p>
                    <p className="flex justify-between gap-4">
                      {p.categoryHorizon}
                      <span className="tabular">{formatEurHundreds(row.horizon)}</span>
                    </p>
                  </div>
                );
              }}
            />

            <Bar dataKey="today" name={p.categoryToday} radius={2} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.colour} fillOpacity={0.4} />
              ))}
            </Bar>
            <Bar dataKey="horizon" name={p.categoryHorizon} radius={2} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.name} fill={d.colour} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="flex justify-center gap-4 text-xs">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-fg opacity-40" />
          {p.categoryToday}
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="h-2.5 w-2.5 rounded-sm bg-fg" />
          {p.categoryHorizon}
        </span>
      </p>
    </div>
  );
}
