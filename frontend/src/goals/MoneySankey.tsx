import {
  ResponsiveContainer,
  Sankey,
  type SankeyLinkProps,
  type SankeyNodeProps,
  Tooltip,
} from "recharts";
import type { SankeyOut } from "../api/generated";
import { Card, DataTable, TOOLTIP } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole } from "../lib/money";
import { monthLabel } from "../lib/months";
import { wealthColour } from "../wealth/colours";
import { tierColour } from "./shared";

const FREE = "var(--color-neutral-400)";

type Node = { key: string; label: string; amount: number; fill: string; depth: number };

/**
 * F-ANA-5: categories to their lines, and each line to the goals' envelopes on it and its free
 * part, at the reference month. Lines wear their category's colour, goals their tier's, the
 * free part grey; every node is labelled and the table says each envelope in words.
 */
export function MoneySankey({
  sankey,
  allAssets,
  onAllAssets,
}: {
  sankey: SankeyOut;
  allAssets: boolean;
  onAllAssets: (all: boolean) => void;
}) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const colourOf = new Map(sankey.categories.map((c) => [c.category_id, c.colour]));
  const categoryName = new Map(sankey.categories.map((c) => [c.category_id, c.name]));
  const goals = [...new Map(sankey.flows.map((f) => [f.goal_id, f])).values()];
  const free = sankey.lines.reduce((sum, l) => sum + Number(l.free), 0);

  const nodes: Node[] = [
    ...sankey.categories.map((c) => ({
      key: `c:${c.category_id}`,
      label: c.name,
      amount: Number(c.amount),
      fill: wealthColour(c.colour),
      depth: 0,
    })),
    ...sankey.lines.map((l) => ({
      key: `l:${l.line_id}`,
      label: l.name,
      amount: Number(l.amount),
      fill: wealthColour(colourOf.get(l.category_id) ?? "exotic"),
      depth: 1,
    })),
    ...goals.map((g) => ({
      key: `g:${g.goal_id}`,
      label: g.name,
      amount: sankey.flows
        .filter((f) => f.goal_id === g.goal_id)
        .reduce((sum, f) => sum + Number(f.amount), 0),
      fill: tierColour(g.tier),
      depth: 2,
    })),
    ...(free > 0 ? [{ key: "free", label: a.free, amount: free, fill: FREE, depth: 2 }] : []),
  ];
  const at = new Map(nodes.map((n, i) => [n.key, i]));
  const node = (key: string) => at.get(key) ?? 0;
  const lineFill = (lineId: string) => {
    const line = sankey.lines.find((l) => l.line_id === lineId);
    return wealthColour(colourOf.get(line?.category_id ?? "") ?? "exotic");
  };
  const links = [
    ...sankey.lines.map((l) => ({
      source: node(`c:${l.category_id}`),
      target: node(`l:${l.line_id}`),
      value: Number(l.amount),
      fill: lineFill(l.line_id),
    })),
    ...sankey.flows.map((f) => ({
      source: node(`l:${f.line_id}`),
      target: node(`g:${f.goal_id}`),
      value: Number(f.amount),
      fill: lineFill(f.line_id),
    })),
    ...sankey.lines
      .filter((l) => Number(l.free) > 0)
      .map((l) => ({
        source: node(`l:${l.line_id}`),
        target: node("free"),
        value: Number(l.free),
        fill: FREE,
      })),
  ];
  const rows = Math.max(...[0, 1, 2].map((d) => nodes.filter((n) => n.depth === d).length));
  const height = Math.max(260, rows * 40 + 48);

  const NodeMark = ({ x, y, width, height: h, payload }: SankeyNodeProps) => {
    const n = payload as unknown as Node;
    const left = n.depth === 0;
    return (
      <g>
        <rect x={x} y={y} width={width} height={Math.max(h, 2)} rx={2} fill={n.fill} />
        <text
          x={left ? x - 8 : x + width + 8}
          y={y + h / 2}
          textAnchor={left ? "end" : "start"}
          dominantBaseline="middle"
          fontSize={12}
          fill="var(--color-fg)"
          // A halo in the card's colour keeps a label readable over the flows it sits on.
          stroke="var(--color-surface)"
          strokeWidth={3}
          strokeLinejoin="round"
          paintOrder="stroke"
        >
          {n.label}
          <tspan fill="var(--color-muted)"> {formatEurWhole(n.amount)}</tspan>
        </text>
      </g>
    );
  };

  const LinkMark = (props: SankeyLinkProps) => {
    const { sourceX, targetX, sourceY, targetY, sourceControlX, targetControlX, linkWidth } = props;
    const fill = (props.payload as unknown as { fill: string }).fill;
    return (
      <path
        d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
        fill="none"
        stroke={fill}
        strokeOpacity={0.35}
        strokeWidth={Math.max(linkWidth, 1)}
      />
    );
  };

  const goalName = new Map(goals.map((g) => [g.goal_id, g.name]));
  const tableRows = sankey.lines.flatMap((l) => [
    ...sankey.flows
      .filter((f) => f.line_id === l.line_id)
      .map((f) => [
        categoryName.get(l.category_id) ?? "",
        l.name,
        goalName.get(f.goal_id) ?? "",
        formatEurWhole(f.amount),
      ]),
    ...(Number(l.free) > 0
      ? [[categoryName.get(l.category_id) ?? "", l.name, a.free, formatEurWhole(l.free)]]
      : []),
  ]);

  return (
    <Card title={a.sankey} subtitle={a.sankeyHelp(monthLabel(sankey.month))}>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={allAssets}
          onChange={(e) => onAllAssets(e.target.checked)}
        />
        {a.allAssets}
      </label>
      {sankey.lines.length === 0 ? (
        <p className="text-sm text-muted">{a.noSankey}</p>
      ) : (
        <div className="overflow-x-auto">
          <div style={{ height, minWidth: 720 }} role="img" aria-label={a.sankeyLabel}>
            <ResponsiveContainer width="100%" height="100%">
              <Sankey
                data={{ nodes, links }}
                nameKey="label"
                node={NodeMark}
                link={LinkMark}
                nodeWidth={12}
                nodePadding={16}
                sort={false}
                margin={{ top: 16, right: 200, bottom: 8, left: 180 }}
              >
                <Tooltip {...TOOLTIP} />
              </Sankey>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {sankey.elsewhere.length > 0 && (
        <p className="text-sm text-muted">
          {a.elsewhere(
            sankey.elsewhere.map((e) => `${e.name} ${formatEurWhole(e.amount)}`).join(", "),
          )}
        </p>
      )}
      <p className="text-xs text-muted">{a.freeHelp}</p>
      <DataTable
        label={a.sankeyTable}
        head={[a.category, a.line, a.holds, a.amount]}
        rows={tableRows}
      />
    </Card>
  );
}
