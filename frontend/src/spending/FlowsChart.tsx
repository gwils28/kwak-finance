import {
  ResponsiveContainer,
  Sankey,
  type SankeyLinkProps,
  type SankeyNodeProps,
  Tooltip,
} from "recharts";
import type { SpendingFlowOut } from "../api/generated";
import { Card, DataTable, TOOLTIP } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent } from "../lib/money";

type Role = "income" | "spent" | "overspent" | "saved" | "deficit" | "other";

const FILL: Record<Role, string> = {
  income: "var(--color-flow-in)",
  spent: "var(--color-flow-spent)",
  overspent: "var(--color-flow-overspent)",
  saved: "var(--color-flow-saved)",
  deficit: "var(--color-flow-overspent)",
  other: "var(--color-flow-other)",
};
const ORDER: Role[] = ["income", "spent", "overspent", "saved", "deficit", "other"];

type Entry = {
  key: string;
  label: string;
  side: "in" | "out";
  role: Role;
  amount: number;
  over: boolean;
};

function roleOf(f: SpendingFlowOut): Role {
  if (f.kind === "deficit") return "deficit";
  if (f.side === "in") return "income";
  if (f.kind === "spending") return f.over ? "overspent" : "spent";
  if (f.kind === "saved") return "saved";
  return "other";
}

/**
 * Where a report's money came from and went (F-DSH-2): income by category and money taken
 * back from savings on the left, spending by category, savings and the rest on the right.
 * Every node is labelled, the colours have a legend, and the table says each flow's status in
 * words.
 */
export function FlowsChart({ flows }: { flows: SpendingFlowOut[] }) {
  const { t } = useI18n();
  const w = t.reports.flows;
  const entries: Entry[] = flows.map((f, i) => ({
    key: `${f.side}:${f.kind}:${f.category_id ?? i}`,
    // Income and spending flows are categories: their name; the others are named here.
    label: f.kind === "spending" || f.category_id ? (f.name ?? "") : w[f.kind],
    side: f.side,
    role: roleOf(f),
    amount: Number(f.amount),
    over: f.over,
  }));
  const bySize = (side: "in" | "out") => {
    const all = entries.filter((e) => e.side === side);
    // The categories' flows, income or spending, the largest first; then the others.
    const byCategory = all.filter((e) => ["income", "spent", "overspent"].includes(e.role));
    return [
      ...byCategory.sort((a, b) => b.amount - a.amount),
      ...all.filter((e) => !byCategory.includes(e)),
    ];
  };
  const left = bySize("in");
  const right = bySize("out");
  const total = left.reduce((sum, e) => sum + e.amount, 0);
  const hub = left.length;
  const data = {
    nodes: [...left, { key: "hub", label: w.hub, role: "hub", amount: total }, ...right],
    links: [
      ...left.map((e, i) => ({ source: i, target: hub, value: e.amount, role: e.role })),
      ...right.map((e, i) => ({ source: hub, target: hub + 1 + i, value: e.amount, role: e.role })),
    ],
  };
  const height = Math.max(240, Math.max(left.length, right.length) * 44 + 40);
  const shown = [...left, ...right];

  const Node = ({ x, y, width, height: h, payload, index }: SankeyNodeProps) => {
    const node = payload as unknown as Entry;
    const isLeft = index < hub;
    const isHub = index === hub;
    return (
      <g>
        {/* The hub is neither a flow nor in the legend: a neutral fill. */}
        <rect
          x={x}
          y={y}
          width={width}
          height={Math.max(h, 2)}
          rx={2}
          fill={isHub ? "var(--color-muted)" : FILL[node.role]}
        />
        <text
          x={isHub ? x + width / 2 : isLeft ? x - 8 : x + width + 8}
          y={isHub ? y - 8 : y + h / 2}
          textAnchor={isHub ? "middle" : isLeft ? "end" : "start"}
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
    const role = (payload as unknown as { role: Role }).role;
    return (
      <path
        d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
        fill="none"
        stroke={FILL[role]}
        strokeOpacity={0.35}
        strokeWidth={Math.max(linkWidth, 1)}
      />
    );
  };

  return (
    <Card title={w.title} subtitle={w.help}>
      {total === 0 ? (
        <p className="text-sm text-muted">{w.none}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <div style={{ height, minWidth: 640 }}>
              <ResponsiveContainer width="100%" height="100%">
                <Sankey
                  data={data}
                  nameKey="label"
                  node={Node}
                  link={Link}
                  nodeWidth={12}
                  nodePadding={16}
                  sort={false}
                  margin={{ top: 24, right: 200, bottom: 8, left: 200 }}
                >
                  <Tooltip {...TOOLTIP} />
                </Sankey>
              </ResponsiveContainer>
            </div>
          </div>
          <ul aria-label={w.legend} className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {ORDER.filter((role) => shown.some((e) => e.role === role)).map((role) => (
              <li key={role} className="flex items-center gap-1.5">
                <span
                  className="inline-block h-3 w-3 rounded-sm"
                  style={{ background: FILL[role] }}
                />
                {w.roles[role]}
              </li>
            ))}
          </ul>
        </>
      )}
      <DataTable
        label={w.title}
        head={[w.side, w.flow, w.amount, w.share, w.status]}
        rows={shown.map((e) => [
          e.side === "in" ? w.in : w.out,
          e.label,
          formatEurWhole(e.amount),
          formatPercent(total ? e.amount / total : 0),
          e.role === "spent" || e.role === "overspent"
            ? e.over
              ? w.overTarget
              : w.withinTarget
            : "",
        ])}
      />
    </Card>
  );
}
