/**
 * Plan steering charts (F-DSH-6), in the dashboard's style: each has its table twin.
 */
import { type ReactNode, useId, useState } from "react";
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
  Sankey,
  type SankeyLinkProps,
  type SankeyNodeProps,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BudgetStatus,
  CumulativeOut,
  FlowOut,
  ReviewOut,
  ReviewRowOut,
} from "../api/generated";
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
import { formatEurWhole, formatPercent, formatPercentSigned } from "../lib/money";

const STATUS_FILL: Record<BudgetStatus, string> = {
  under: "var(--color-chart-under)",
  on: "var(--color-chart-on)",
  over: "var(--color-chart-over)",
  ahead: "var(--color-chart-under)",
  behind: "var(--color-chart-over)",
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

type FlowRole =
  | "income"
  | "spent"
  | "spending"
  | "overspent"
  | "saved"
  | "savedBehind"
  | "deficit"
  | "other";
type FlowStatus = "withinTarget" | "overTarget" | "objectiveMet" | "belowObjective";

const ROLE_FILL: Record<FlowRole, string> = {
  income: "var(--color-flow-in)",
  spent: "var(--color-flow-spent)",
  spending: "var(--color-flow-spent)",
  overspent: "var(--color-flow-overspent)",
  saved: "var(--color-flow-saved)",
  savedBehind: "var(--color-flow-saved-behind)",
  deficit: "var(--color-flow-overspent)",
  other: "var(--color-flow-other)",
};
const ROLE_ORDER: FlowRole[] = [
  "income",
  "spent",
  "spending",
  "overspent",
  "saved",
  "savedBehind",
  "deficit",
  "other",
];

/** What the review says of a flow's category: spending against its target, savings
 * against the objectives. Without a target, or without a review (a report), nothing. */
type Judged = { role: FlowRole; status: FlowStatus | null };

function judge(f: FlowOut, categoryId: string | null, review?: ReviewOut): Judged {
  if (f.kind === "deficit") return { role: "deficit", status: null };
  // Everything coming in is money in: income, transfers paid in, savings taken back.
  if (f.side === "in") return { role: "income", status: null };
  if (!review) {
    if (f.kind === "saved") return { role: "saved", status: null };
    const spending = f.kind === "spending" || f.kind === "income" || f.kind === "uncategorised";
    return { role: spending ? "spending" : "other", status: null };
  }
  if (f.kind === "saved") {
    const status = review.savings_total.status;
    if (status === "behind") return { role: "savedBehind", status: "belowObjective" };
    return { role: "saved", status: status === "none" ? null : "objectiveMet" };
  }
  if (f.kind === "spending") {
    const status = review.rows.find((r) => r.category_id === categoryId)?.status;
    if (status === "over") return { role: "overspent", status: "overTarget" };
    if (status === "under" || status === "on") return { role: "spent", status: "withinTarget" };
    return { role: "spent", status: null };
  }
  if (f.kind === "income" || f.kind === "uncategorised") return { role: "spent", status: null };
  return { role: "other", status: null };
}

type FlowEntry = {
  key: string;
  label: string;
  side: "in" | "out";
  role: FlowRole;
  status: FlowStatus | null;
  amount: number;
};

/**
 * One entry per Sankey node: income by category, spending by top-level category (or by
 * subcategory with `detail`), then transfers, savings and what is left.
 */
function flowEntries(
  flows: FlowOut[],
  detail: boolean,
  name: (f: FlowOut) => string,
  review?: ReviewOut,
) {
  const entries = new Map<string, FlowEntry>();
  for (const f of flows) {
    const grouped = f.kind === "spending" && !detail && f.parent_id;
    const categoryId = grouped ? f.parent_id : f.category_id;
    const key = `${f.side}:${f.kind}:${categoryId ?? ""}`;
    const label = grouped ? (f.parent_name as string) : name(f);
    const entry = entries.get(key) ?? {
      key,
      label,
      side: f.side,
      ...judge(f, categoryId, review),
      amount: 0,
    };
    entry.amount += Number(f.amount);
    entries.set(key, entry);
  }
  const byCategory = (e: FlowEntry) => e.key.includes(":income:") || e.key.includes(":spending:");
  const sorted = (side: "in" | "out") => {
    const all = [...entries.values()].filter((e) => e.side === side);
    return [
      ...all.filter(byCategory).sort((a, b) => b.amount - a.amount),
      ...all.filter((e) => !byCategory(e)),
    ];
  };
  return { left: sorted("in"), right: sorted("out") };
}

const NODE_WIDTH = 12;

/**
 * Where the money of a plan, or of a report's period, came from and went (F-DSH-2), every node
 * labelled, with its table. Without a review, flows have no status.
 */
export function FlowsChart({
  flows,
  review,
  help,
  none,
}: {
  flows: FlowOut[];
  review?: ReviewOut;
  help?: string;
  none?: string;
}) {
  const { t } = useI18n();
  const detailId = useId();
  const [detail, setDetail] = useState(false);
  const name = (f: FlowOut): string => {
    const words = t.review.flows;
    if (f.kind === "income" || f.kind === "spending") {
      const crossed = (f.kind === "income") !== (f.side === "in");
      return crossed ? words.crossed(f.name as string) : (f.name as string);
    }
    if (f.kind === "uncategorised")
      return f.side === "in" ? words.uncategorisedIn : words.uncategorised;
    return words[f.kind];
  };
  const { left, right } = flowEntries(flows, detail, name, review);
  const total = left.reduce((sum, e) => sum + e.amount, 0);
  const entries = [...left, ...right];
  const hub = left.length;
  const data = {
    nodes: [
      ...left,
      { key: "hub", label: t.review.flows.hub, role: "other", amount: total },
      ...right,
    ],
    links: [
      ...left.map((e, i) => ({ source: i, target: hub, value: e.amount, role: e.role })),
      ...right.map((e, i) => ({ source: hub, target: hub + 1 + i, value: e.amount, role: e.role })),
    ],
  };
  const height = Math.max(240, Math.max(left.length, right.length) * 44 + 40);

  const Node = ({ x, y, width, height: h, payload, index }: SankeyNodeProps) => {
    const node = payload as unknown as FlowEntry;
    const isLeft = index < hub;
    const isHub = index === hub;
    const textX = isHub ? x + width / 2 : isLeft ? x - 8 : x + width + 8;
    const anchor = isHub ? "middle" : isLeft ? "end" : "start";
    return (
      <g>
        <rect
          x={x}
          y={y}
          width={width}
          height={Math.max(h, 2)}
          rx={2}
          fill={ROLE_FILL[node.role]}
        />
        <text
          x={textX}
          y={isHub ? y - 8 : y + h / 2}
          textAnchor={anchor}
          dominantBaseline={isHub ? "auto" : "middle"}
          fontSize={12}
          fill="var(--color-fg)"
        >
          {node.label}
          <tspan fill="var(--color-muted)"> {formatEurWhole(node.amount)}</tspan>
        </text>
      </g>
    );
  };

  const Link = (props: SankeyLinkProps) => {
    const {
      sourceX,
      targetX,
      sourceY,
      targetY,
      sourceControlX,
      targetControlX,
      linkWidth,
      payload,
    } = props;
    const role = (payload as unknown as { role: FlowRole }).role;
    return (
      <path
        d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
        fill="none"
        stroke={ROLE_FILL[role]}
        strokeOpacity={0.35}
        strokeWidth={Math.max(linkWidth, 1)}
      />
    );
  };

  const toggle = (
    <label htmlFor={detailId} className="flex items-center gap-2 text-sm">
      <input
        id={detailId}
        type="checkbox"
        checked={detail}
        onChange={(e) => setDetail(e.target.checked)}
      />
      {t.review.flows.detail}
    </label>
  );

  return (
    <Card title={t.review.flows.title} subtitle={help ?? t.review.flows.help} aside={toggle}>
      {total === 0 ? (
        <p className="text-sm text-muted">{none ?? t.review.flows.none}</p>
      ) : (
        <div className="overflow-x-auto">
          <div style={{ height, minWidth: 640 }}>
            <ResponsiveContainer width="100%" height="100%">
              <Sankey
                data={data}
                nameKey="label"
                node={Node}
                link={Link}
                nodeWidth={NODE_WIDTH}
                nodePadding={16}
                sort={false}
                margin={{ top: 24, right: 200, bottom: 8, left: 200 }}
              >
                <Tooltip {...TOOLTIP} />
              </Sankey>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {total !== 0 && (
        <ul
          aria-label={t.review.flows.legend}
          className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted"
        >
          {ROLE_ORDER.filter((role) => entries.some((e) => e.role === role)).map((role) => (
            <li key={role} className="flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-3 rounded-sm"
                style={{ background: ROLE_FILL[role] }}
              />
              {t.review.flows.roles[role]}
            </li>
          ))}
        </ul>
      )}
      <DataTable
        label={t.review.flows.title}
        head={[
          t.review.flows.side,
          t.review.flows.flow,
          t.review.flows.amount,
          t.review.flows.share,
          ...(review ? [t.review.flows.status] : []),
        ]}
        rows={entries.map((e) => [
          e.side === "in" ? t.review.flows.in : t.review.flows.out,
          e.label,
          formatEurWhole(e.amount),
          formatPercent(total ? e.amount / total : 0),
          ...(review ? [e.status ? t.review.flows[e.status] : ""] : []),
        ])}
      />
    </Card>
  );
}
