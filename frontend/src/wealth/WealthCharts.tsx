/**
 * The wealth charts (F-WLT-6), drawn from the matrix on screen: net worth over time on its own
 * scale, the allocation of a chosen month as a sunburst, and what moved net worth. Categories
 * keep their `wealth-*` colour everywhere; every chart has its table, and the sunburst reads
 * the pointed or focused mark out in words.
 */
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { listWealthCategories, type WealthMatrixOut } from "../api/generated";
import { AXIS, Card, DataTable, GRID, TOOLTIP } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";
import { allocation, bridge, fittedAxis, history, netWorth } from "./chartData";
import { wealthColour } from "./colours";

const SURFACE = "var(--color-surface)";
const FG = "var(--color-fg)";

export function WealthCharts({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const id = useId();
  // The month the allocation charts show: the last one by default, or when off the window.
  const [chosen, setChosen] = useState<string | null>(null);
  const month = chosen && matrix.months.includes(chosen) ? chosen : (matrix.months.at(-1) ?? "");
  const index = matrix.months.indexOf(month);
  return (
    <div className="flex flex-col gap-4">
      <History matrix={matrix} />
      <label htmlFor={id} className="flex w-fit flex-col gap-1 text-sm font-medium">
        {t.wealth.charts.monthShown}
        <select
          id={id}
          className="rounded-md border border-border bg-surface px-3 py-2"
          value={month}
          onChange={(e) => setChosen(e.target.value)}
        >
          {matrix.months.map((m) => (
            <option key={m} value={m}>
              {monthLabel(m)}
            </option>
          ))}
        </select>
      </label>
      <Allocation matrix={matrix} index={index} />
      <Bridge matrix={matrix} />
    </div>
  );
}

const axisEur = (v: number) => formatEurWhole(v);

/** The real-estate categories (their preset), which can flatten every other move. */
function useRealEstate(): Set<string> {
  const categories = useQuery({
    queryKey: ["wealth", "categories"],
    queryFn: async () => (await listWealthCategories({ throwOnError: true })).data,
  });
  return new Set(
    (categories.data ?? []).filter((c) => c.preset === "real-estate").map((c) => c.id),
  );
}

/**
 * Net worth as a line on an axis fitted to it, not to zero, so a change of a few percent shows;
 * real estate can be taken off. The table keeps each category's total.
 */
function History({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const id = useId();
  const [withoutHome, setWithoutHome] = useState(false);
  const realEstate = useRealEstate();
  const held = matrix.categories.filter((cat) => cat.subtotals.some((v) => Number(v) !== 0));
  const homes = new Set(
    held.filter((cat) => cat.kind === "asset" && realEstate.has(cat.id)).map((cat) => cat.id),
  );
  const off = withoutHome && homes.size > 0;
  const points = netWorth(matrix, off ? homes : new Set());
  const rows = history(matrix);
  const axis = fittedAxis(points.map((p) => p.net));
  const label = off ? c.netWithoutHome : c.net;
  return (
    <Card title={c.history} subtitle={c.historyHelp}>
      {homes.size > 0 && (
        <label htmlFor={id} className="flex w-fit items-center gap-2 text-sm">
          <input
            id={id}
            type="checkbox"
            checked={withoutHome}
            onChange={(e) => setWithoutHome(e.target.checked)}
          />
          {c.withoutHome}
        </label>
      )}
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
            <YAxis
              tickFormatter={axisEur}
              width={84}
              domain={axis.domain}
              ticks={axis.ticks}
              allowDataOverflow
              {...AXIS}
            />
            <Tooltip
              {...TOOLTIP}
              itemStyle={{ color: FG }}
              labelFormatter={(m) => monthLabel(String(m))}
              formatter={(v) => [formatEurWhole(Number(v)), label]}
            />
            <Line
              dataKey="net"
              name={label}
              stroke={FG}
              strokeWidth={2}
              dot={{ r: 4, fill: FG, stroke: SURFACE, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={c.historyTable}
        head={[c.month, label, ...held.map((cat) => cat.name)]}
        rows={rows.map((row, i) => [
          monthLabel(row.month),
          formatEurWhole(points[i]?.net ?? 0),
          ...held.map((cat) => formatEurWhole(Number(row[cat.id]))),
        ])}
      />
    </Card>
  );
}

/** An annular sector, angles in radians clockwise from the top. */
function arc(cx: number, r0: number, r1: number, a0: number, a1: number): string {
  const end = Math.min(a1, a0 + 2 * Math.PI - 1e-4);
  const at = (r: number, a: number) =>
    `${(cx + r * Math.sin(a)).toFixed(2)} ${(cx - r * Math.cos(a)).toFixed(2)}`;
  const large = end - a0 > Math.PI ? 1 : 0;
  return [
    `M ${at(r1, a0)}`,
    `A ${r1} ${r1} 0 ${large} 1 ${at(r1, end)}`,
    `L ${at(r0, end)}`,
    `A ${r0} ${r0} 0 ${large} 0 ${at(r0, a0)}`,
    "Z",
  ].join(" ");
}

type Pointed = { id: string; text: string } | null;

/** A mark that reads itself out when pointed at or focused. */
function markProps(id: string, text: string, setPointed: (p: Pointed) => void) {
  return {
    tabIndex: 0,
    role: "img",
    "aria-label": text,
    className: "cursor-default outline-none focus-visible:stroke-[var(--color-fg)]",
    onMouseEnter: () => setPointed({ id, text }),
    onMouseLeave: () => setPointed(null),
    onFocus: () => setPointed({ id, text }),
    onBlur: () => setPointed(null),
  };
}

function Allocation({ matrix, index }: { matrix: WealthMatrixOut; index: number }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const [pointed, setPointed] = useState<Pointed>(null);
  const ids = { sunburst: useId() };
  const { total, categories } = allocation(matrix, index);
  const month = monthLabel(matrix.months[index] ?? "");
  const SIZE = 300;
  const C = SIZE / 2;
  let angle = 0;
  const sectors = categories.flatMap((cat) => {
    const a0 = angle;
    const a1 = a0 + cat.share * 2 * Math.PI;
    angle = a1;
    let inner = a0;
    const lines = cat.lines.map((l) => {
      const b0 = inner;
      inner = b0 + l.share * 2 * Math.PI;
      return { key: l.id, d: arc(C, 106, 146, b0, inner), fill: cat.colour, outer: true, slice: l };
    });
    return [
      { key: cat.id, d: arc(C, 56, 104, a0, a1), fill: cat.colour, outer: false, slice: cat },
      ...lines,
    ];
  });
  const describe = (name: string, value: number, share: number) =>
    `${name}: ${formatEurWhole(value)} · ${formatPercent(share)}`;
  return (
    <Card title={c.allocation} subtitle={c.allocationHelp(month)}>
      {total <= 0 ? (
        <p className="text-sm text-muted">{c.noAssets}</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-4">
            <svg
              viewBox={`0 0 ${SIZE} ${SIZE}`}
              aria-labelledby={ids.sunburst}
              className="mx-auto w-full max-w-72"
            >
              <title id={ids.sunburst}>{c.sunburst}</title>
              {sectors.map((s) => (
                <path
                  key={s.key}
                  d={s.d}
                  fill={wealthColour(s.fill)}
                  fillOpacity={s.outer ? 0.7 : 1}
                  stroke={SURFACE}
                  strokeWidth={2}
                  opacity={pointed && pointed.id !== s.key ? 0.35 : 1}
                  {...markProps(
                    s.key,
                    describe(s.slice.name, s.slice.value, s.slice.share),
                    setPointed,
                  )}
                />
              ))}
              <text x={C} y={C - 6} textAnchor="middle" fontSize={12} fill="var(--color-muted)">
                {t.wealth.gross}
              </text>
              <text x={C} y={C + 14} textAnchor="middle" fontSize={16} fontWeight={600} fill={FG}>
                {formatEurWhole(total)}
              </text>
            </svg>
            <ul className="flex min-w-40 flex-1 flex-col gap-1 text-sm">
              {categories.map((cat) => (
                <li key={cat.id} className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="inline-block size-3 shrink-0 rounded-sm"
                    style={{ background: wealthColour(cat.colour) }}
                  />
                  <span className="flex-1">{cat.name}</span>
                  <span className="tabular-nums text-muted">{formatPercent(cat.share)}</span>
                </li>
              ))}
            </ul>
          </div>
          <p aria-live="polite" className="min-h-5 text-sm">
            {pointed?.text}
          </p>
          <DataTable
            label={c.allocationTable}
            head={[c.line, c.value, c.share]}
            rows={categories.flatMap((cat) => [
              [cat.name, formatEurWhole(cat.value), formatPercent(cat.share)],
              ...cat.lines.map((l) => [
                `${cat.name} · ${l.name}`,
                formatEurWhole(l.value),
                formatPercent(l.share),
              ]),
            ])}
          />
        </>
      )}
    </Card>
  );
}

const UP = "var(--color-chart-under)";
const DOWN = "var(--color-chart-over)";

/**
 * Each category's contribution to the change of net worth, as bars from zero: a waterfall from
 * zero would crush the steps against the totals. The totals are in the subtitle and the table.
 */
function Bridge({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const steps = bridge(matrix);
  if (!steps) return null;
  const from = monthLabel(matrix.months[0] ?? "");
  const to = monthLabel(matrix.months.at(-1) ?? "");
  const names = new Map(matrix.categories.map((cat) => [cat.id, cat.name]));
  const start = steps[0]?.to ?? 0;
  const end = steps.at(-1)?.to ?? 0;
  const moves = steps
    .filter((s) => s.kind === "up" || s.kind === "down")
    .map((s) => ({ ...s, name: names.get(s.key) ?? "", label: formatEurSigned(s.delta) }));
  return (
    <Card
      title={c.bridge}
      subtitle={c.bridgeHelp(
        formatEurWhole(start),
        from,
        formatEurWhole(end),
        to,
        formatEurSigned(end - start),
      )}
    >
      {moves.length > 0 && (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={moves} margin={{ top: 24, right: 16, bottom: 0, left: 8 }}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="name" interval={0} {...AXIS} />
              <YAxis tickFormatter={axisEur} width={84} {...AXIS} />
              <ReferenceLine y={0} stroke="var(--color-muted)" />
              <Tooltip
                {...TOOLTIP}
                itemStyle={{ color: FG }}
                formatter={(_v, _n, item) => [String(item.payload.label), c.contribution]}
              />
              <Bar dataKey="delta" isAnimationActive={false} radius={4}>
                {moves.map((d) => (
                  <Cell key={d.key} fill={d.kind === "up" ? UP : DOWN} />
                ))}
                <LabelList dataKey="label" position="top" fontSize={12} fill={FG} />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <DataTable
        label={c.bridgeTable}
        head={[c.category, c.contribution]}
        rows={[
          [from, formatEurWhole(start)],
          ...moves.map((d) => [d.name, d.label]),
          [to, formatEurWhole(end)],
        ]}
      />
    </Card>
  );
}
