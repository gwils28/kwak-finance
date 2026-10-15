/**
 * The wealth charts (F-WLT-6), drawn from the matrix on screen: net worth over time, the
 * allocation as a sunburst, who holds what as a Marimekko, and what moved net worth. Categories
 * keep their `wealth-*` colour everywhere; every chart has its table, and the sunburst and the
 * Marimekko read the pointed or focused mark out in words.
 */
import { useSuspenseQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { WealthMatrixOut } from "../api/generated";
import { meQuery } from "../auth/session";
import { AXIS, Card, DataTable, GRID, legendText, TOOLTIP } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";
import { allocation, bridge, type HoldingColumn, history, holdings, JOINT } from "./chartData";

/** A category's colour: its `wealth-*` token (spec §7). */
export const wealthColour = (key: string) => `var(--color-wealth-${key})`;

const SURFACE = "var(--color-surface)";
const FG = "var(--color-fg)";

export function WealthCharts({ matrix }: { matrix: WealthMatrixOut }) {
  return (
    <div className="flex flex-col gap-4">
      <History matrix={matrix} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Allocation matrix={matrix} />
        <Holdings matrix={matrix} />
      </div>
      <Bridge matrix={matrix} />
    </div>
  );
}

const axisEur = (v: number) => formatEurWhole(v);

function History({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const rows = history(matrix);
  const held = matrix.categories.filter((cat) => cat.id in (rows[0] ?? {}));
  const names = new Map(held.map((cat) => [cat.id, cat.name]));
  const order = new Map(held.map((cat, i) => [cat.id, i]));
  return (
    <Card title={c.history} subtitle={c.historyHelp}>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={rows}
            stackOffset="sign"
            margin={{ top: 8, right: 16, bottom: 0, left: 8 }}
          >
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
            <YAxis tickFormatter={axisEur} width={84} {...AXIS} />
            <Tooltip
              {...TOOLTIP}
              // Text in the text colour, in the stack's order (the matrix's), net worth last.
              itemStyle={{ color: FG }}
              itemSorter={(item) => order.get(String(item.dataKey)) ?? order.size}
              labelFormatter={(m) => monthLabel(String(m))}
              formatter={(v, name) => [formatEurWhole(Number(v)), names.get(String(name)) ?? c.net]}
            />
            <Legend
              itemSorter={null}
              formatter={(id: string) => legendText(names.get(id) ?? c.net)}
              wrapperStyle={{ fontSize: 12 }}
            />
            {held.map((cat) => (
              <Bar
                key={cat.id}
                dataKey={cat.id}
                stackId="wealth"
                fill={wealthColour(cat.colour)}
                stroke={SURFACE}
                strokeWidth={1}
                isAnimationActive={false}
              />
            ))}
            <Line
              dataKey="net"
              name="net"
              stroke={FG}
              strokeWidth={2}
              dot={{ r: 4, fill: FG, stroke: SURFACE, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <DataTable
        label={c.historyTable}
        head={[c.month, ...held.map((cat) => cat.name), c.net]}
        rows={rows.map((row) => [
          monthLabel(row.month),
          ...held.map((cat) => formatEurWhole(Number(row[cat.id]))),
          formatEurWhole(row.net),
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

function Allocation({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const [pointed, setPointed] = useState<Pointed>(null);
  const ids = { sunburst: useId() };
  const { total, categories } = allocation(matrix);
  const month = monthLabel(matrix.months.at(-1) ?? "");
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
                  <span className="tabular text-muted">{formatPercent(cat.share)}</span>
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

/** Holders' shades of the category colour: the viewer full, the joint holding the palest. */
/**
 * How a holder's part is filled: the viewer in the category's colour, other members in a
 * lighter shade, the joint holding hatched (a texture, not a darker shade: it would sink into
 * the dark surface).
 */
const holderFill = (holder: string, viewerId: string, colour: string, hatch: string) =>
  holder === JOINT
    ? { fill: `url(#${hatch})` }
    : { fill: colour, fillOpacity: holder === viewerId ? 1 : 0.55 };

/** React's ids hold characters a `url(#…)` reference does not take. */
const svgId = (id: string) => `w${id.replace(/[^a-zA-Z0-9_-]/g, "")}`;

function HatchSwatch({ colour }: { colour: string }) {
  const id = svgId(useId());
  return (
    <svg aria-hidden viewBox="0 0 12 12" className="size-3 rounded-sm">
      <defs>
        <Hatch id={id} colour={colour} />
      </defs>
      <rect width={12} height={12} fill={`url(#${id})`} />
    </svg>
  );
}

function Hatch({ id, colour }: { id: string; colour: string }) {
  return (
    <pattern
      id={id}
      width={6}
      height={6}
      patternUnits="userSpaceOnUse"
      patternTransform="rotate(45)"
    >
      <rect width={6} height={6} fill={colour} fillOpacity={0.3} />
      <line x1={0} y1={0} x2={0} y2={6} stroke={colour} strokeWidth={4} />
    </pattern>
  );
}

function Holdings({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const c = t.wealth.charts;
  const { data: user } = useSuspenseQuery(meQuery);
  const [pointed, setPointed] = useState<Pointed>(null);
  const ids = { marimekko: svgId(useId()) };
  const { holders, columns } = holdings(matrix, user.id);
  const month = monthLabel(matrix.months.at(-1) ?? "");
  const holderName = (key: string) =>
    key === JOINT ? c.joint : (holders.find((h) => h.key === key)?.name ?? "");
  const W = 640;
  const H = 220;
  const GAP = 2;
  let x = 0;
  const placed = columns.map((col) => {
    const left = x;
    x += col.share * W;
    return { col, left, width: Math.max(col.share * W - GAP, 1) };
  });
  const describe = (col: HoldingColumn, holder: string, value: number, share: number) =>
    `${col.name} · ${holderName(holder)}: ${formatEurWhole(value)} · ${c.ofCategory(formatPercent(share), col.name)}`;
  return (
    <Card title={c.holdings} subtitle={c.holdingsHelp(month)}>
      {columns.length === 0 ? (
        <p className="text-sm text-muted">{c.noAssets}</p>
      ) : (
        <>
          <ul className="flex flex-wrap gap-4 text-sm">
            {holders.map((h) => (
              <li key={h.key} className="flex items-center gap-2">
                {h.key === JOINT ? (
                  <HatchSwatch colour={FG} />
                ) : (
                  <span
                    aria-hidden
                    className="inline-block size-3 rounded-sm"
                    style={{ background: FG, opacity: h.key === user.id ? 1 : 0.55 }}
                  />
                )}
                {holderName(h.key)}
              </li>
            ))}
          </ul>
          <svg viewBox={`0 0 ${W} ${H + 40}`} aria-labelledby={ids.marimekko} className="w-full">
            <title id={ids.marimekko}>{c.marimekko}</title>
            <defs>
              {columns.map((col) => (
                <Hatch
                  key={col.id}
                  id={`${ids.marimekko}-${col.id}`}
                  colour={wealthColour(col.colour)}
                />
              ))}
            </defs>
            {placed.map(({ col, left, width }) => {
              let bottom = H;
              return (
                <g key={col.id}>
                  {col.parts.map((part) => {
                    const height = Math.max(part.share * H - GAP, 1);
                    const top = bottom - part.share * H;
                    bottom = top;
                    const key = `${col.id}-${part.holder}`;
                    return (
                      <rect
                        key={key}
                        x={left}
                        y={top + GAP}
                        width={width}
                        height={height}
                        rx={2}
                        {...holderFill(
                          part.holder,
                          user.id,
                          wealthColour(col.colour),
                          `${ids.marimekko}-${col.id}`,
                        )}
                        stroke={pointed?.id === key ? FG : "none"}
                        strokeWidth={2}
                        {...markProps(
                          key,
                          describe(col, part.holder, part.value, part.share),
                          setPointed,
                        )}
                      />
                    );
                  })}
                  {width >= 56 && (
                    <>
                      <text
                        x={left + width / 2}
                        y={H + 18}
                        textAnchor="middle"
                        fontSize={12}
                        fill={FG}
                      >
                        {col.name.length > width / 7
                          ? `${col.name.slice(0, Math.floor(width / 7) - 1)}…`
                          : col.name}
                      </text>
                      <text
                        x={left + width / 2}
                        y={H + 34}
                        textAnchor="middle"
                        fontSize={11}
                        fill="var(--color-muted)"
                      >
                        {formatPercent(col.share)}
                      </text>
                    </>
                  )}
                </g>
              );
            })}
          </svg>
          <p aria-live="polite" className="min-h-5 text-sm">
            {pointed?.text}
          </p>
          <DataTable
            label={c.holdingsTable}
            head={[c.holder, c.value, c.share]}
            rows={columns.flatMap((col) =>
              col.parts.map((part) => [
                `${col.name} · ${holderName(part.holder)}`,
                formatEurWhole(part.value),
                c.ofCategory(formatPercent(part.share), col.name),
              ]),
            )}
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
