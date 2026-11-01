/**
 * The retirement's charts (F-RET-4): the members' timeline in HTML, the income once retired and
 * the fan of net worth with Recharts. Colours are the `retirement-*` and `projection-*` tokens
 * (spec §7); every chart keeps its legend or labels and a table twin.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RetirementPlanOut } from "../api/generated";
import { AXIS, GRID, legendText } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurCompact, formatEurHundreds } from "../lib/money";
import { monthLabel } from "../lib/months";

export const R = {
  pensions: "var(--color-retirement-pensions)",
  withdrawal: "var(--color-retirement-withdrawal)",
  spending: "var(--color-fg)",
  liquid: "var(--color-retirement-liquid)",
  median: "var(--color-projection-median)",
  inner: "var(--color-projection-band-inner)",
  outer: "var(--color-projection-band-outer)",
  marker: "var(--color-neutral-500)",
  muted: "var(--color-muted)",
};
export const PEOPLE = ["var(--color-retirement-person-1)", "var(--color-retirement-person-2)"];

export function personColour(index: number): string {
  return PEOPLE[index % PEOPLE.length] ?? PEOPLE[0] ?? R.muted;
}

function year(month: string): number {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return y + (m - 1) / 12;
}

/** One tick a year at most, every 5 or 10 years over long horizons. */
function yearTicks(months: string[]): string[] {
  const years = months.length / 12;
  const step = years > 20 ? 10 : years > 8 ? 5 : years > 3 ? 2 : 1;
  return months.filter((m) => m.endsWith("-01") && Number(m.slice(0, 4)) % step === 0);
}

type TipLine = { colour: string; name: string; value: number };

function Tip({ month, lines }: { month: string; lines: TipLine[] }) {
  return (
    <div className="min-w-48 rounded-md border border-border bg-surface p-2 text-xs shadow-md">
      <p className="mb-1 font-semibold">{monthLabel(month)}</p>
      {lines.map((line) => (
        <p key={line.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: line.colour }}
            />
            {line.name}
          </span>
          <span className="tabular font-medium">{formatEurHundreds(line.value)}</span>
        </p>
      ))}
    </div>
  );
}

/**
 * Each member's working months then pension to the horizon, today, each retirement and the
 * horizon marked (F-RET-4).
 */
export function Timeline({ plan }: { plan: RetirementPlanOut }) {
  const { t } = useI18n();
  const r = t.retirement;
  const start = Number(plan.this_month.slice(0, 4)) - 6;
  const end = Number(plan.horizon.slice(0, 4)) + 1;
  const at = (month: string) => `${(100 * (year(month) - start)) / (end - start)}%`;
  const until = (month: string) => `calc(100% - ${at(month)})`;
  const decades = [];
  for (let y = start; y <= end; y++) if (y % 10 === 0) decades.push(y);
  const marks: { month: string; label: string; place: "now" | "mid" | "end"; low?: boolean }[] = [
    { month: plan.this_month, label: r.today, place: "now" },
  ];
  plan.people.forEach((p, k) => {
    if (p.retirement > plan.this_month) {
      marks.push({
        month: p.retirement,
        label: r.retiresAt(p.name, p.age_at_retirement),
        place: "mid",
        low: k % 2 === 0,
      });
    }
  });
  marks.push({
    month: plan.horizon,
    label: r.horizonAt(plan.youngest, plan.youngest_age_at_horizon),
    place: "end",
  });
  return (
    <div role="img" aria-label={r.lifeChart} className="flex flex-col gap-2 text-xs">
      {plan.people.map((p, k) => {
        const colour = personColour(k);
        const from = p.pension_month > plan.this_month ? p.pension_month : plan.this_month;
        return (
          <div key={p.name} className="flex items-center gap-2">
            <b className="w-20 truncate text-sm">{p.name}</b>
            <div className="relative h-7 flex-1 rounded bg-chart-grid/40">
              {p.retirement > plan.this_month && (
                <span
                  className="absolute inset-y-0 flex items-center overflow-hidden rounded-l border-l-4 px-1 whitespace-nowrap"
                  style={{
                    left: 0,
                    right: until(p.retirement),
                    borderColor: colour,
                    background: `color-mix(in srgb, ${colour} 15%, transparent)`,
                  }}
                >
                  {r.working(formatEurHundreds(p.earnings))}
                </span>
              )}
              <span
                className="absolute inset-y-0 flex items-center overflow-hidden rounded-r px-1 whitespace-nowrap"
                style={{
                  left: at(from),
                  right: until(plan.horizon),
                  background: `color-mix(in srgb, ${colour} 50%, transparent)`,
                }}
              >
                {r.pensionSegment(formatEurHundreds(p.pension))}
              </span>
            </div>
          </div>
        );
      })}
      <div className="ml-22 relative h-16 text-muted">
        {marks.map((m) => (
          <span
            key={m.label}
            className={`absolute border-l border-dashed border-neutral-500 pl-1 whitespace-nowrap ${
              m.place === "end" ? "-translate-x-full border-r border-l-0 pr-1 pl-0" : ""
            }`}
            style={{ left: at(m.month), top: m.low ? "1.25rem" : 0 }}
          >
            {m.label}
          </span>
        ))}
        <span className="absolute inset-x-0 bottom-0 h-4">
          {decades.map((y) => (
            <span
              key={y}
              className="absolute -translate-x-1/2 tabular"
              style={{ left: `${(100 * (y - start)) / (end - start)}%` }}
            >
              {y}
            </span>
          ))}
        </span>
      </div>
    </div>
  );
}

/**
 * From the retirement: the pensions stacked with the sustainable withdrawal, the retirement
 * spending as a line.
 */
export function IncomeChart({ plan }: { plan: RetirementPlanOut }) {
  const { t } = useI18n();
  const r = t.retirement;
  const data = plan.income.map((m) => ({
    month: m.month,
    pensions: Number(m.pensions),
    withdrawal: Number(m.withdrawal),
    spending: Number(m.spending),
  }));
  const tooltip = ({ active, label }: { active?: boolean; label?: string | number }) => {
    const row = active ? data.find((d) => d.month === label) : undefined;
    if (!row) return null;
    return (
      <Tip
        month={row.month}
        lines={[
          { colour: R.pensions, name: r.pensions, value: row.pensions },
          { colour: R.withdrawal, name: r.withdrawal, value: row.withdrawal },
          { colour: R.spending, name: r.spending, value: row.spending },
        ]}
      />
    );
  };
  return (
    <div className="h-72" role="img" aria-label={r.incomeChart}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="month"
            {...AXIS}
            ticks={yearTicks(data.map((d) => d.month))}
            tickFormatter={(m: string) => m.slice(0, 4)}
          />
          <YAxis {...AXIS} width={64} tickFormatter={(v: number) => formatEurCompact(v)} />
          <Tooltip content={tooltip} cursor={{ stroke: R.muted, strokeDasharray: "3 3" }} />
          <Legend
            formatter={legendText}
            wrapperStyle={{ fontSize: 12 }}
            itemSorter={null}
            iconType="circle"
          />
          <Area
            dataKey="pensions"
            name={r.pensions}
            stackId="income"
            stroke={R.pensions}
            fill={R.pensions}
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Area
            dataKey="withdrawal"
            name={r.withdrawal}
            stackId="income"
            stroke={R.withdrawal}
            fill={R.withdrawal}
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Line
            dataKey="spending"
            name={r.spending}
            stroke={R.spending}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** The fan of net worth to the horizon, the liquid holdings' median, the retirement and each
 * later pension's start marked. */
export function FanChart({ plan }: { plan: RetirementPlanOut }) {
  const { t } = useI18n();
  const r = t.retirement;
  const data = plan.months.map((m) => ({
    month: m.month,
    p10: Number(m.p10),
    p50: Number(m.p50),
    p90: Number(m.p90),
    inner: [Number(m.p25), Number(m.p75)] as [number, number],
    outer: [Number(m.p10), Number(m.p90)] as [number, number],
    liquid: Number(m.liquid),
  }));
  const later = plan.people.filter((p) => p.pension_month !== plan.retired);
  const tooltip = ({ active, label }: { active?: boolean; label?: string | number }) => {
    const row = active ? data.find((d) => d.month === label) : undefined;
    if (!row) return null;
    return (
      <Tip
        month={row.month}
        lines={[
          { colour: R.outer, name: r.colP90, value: row.p90 },
          { colour: R.median, name: r.median, value: row.p50 },
          { colour: R.outer, name: r.colP10, value: row.p10 },
          { colour: R.liquid, name: r.liquid, value: row.liquid },
        ]}
      />
    );
  };
  return (
    <div className="h-72" role="img" aria-label={r.fanChart}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 16, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="month"
            {...AXIS}
            ticks={yearTicks(data.map((d) => d.month))}
            tickFormatter={(m: string) => m.slice(0, 4)}
          />
          <YAxis {...AXIS} width={64} tickFormatter={(v: number) => formatEurCompact(v)} />
          <Tooltip content={tooltip} cursor={{ stroke: R.muted, strokeDasharray: "3 3" }} />
          <Legend
            formatter={legendText}
            wrapperStyle={{ fontSize: 12 }}
            itemSorter={null}
            iconType="circle"
          />
          <Area
            dataKey="outer"
            name={r.band1090}
            stroke="none"
            fill={R.outer}
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Area
            dataKey="inner"
            name={r.band2575}
            stroke="none"
            fill={R.inner}
            fillOpacity={1}
            isAnimationActive={false}
          />
          <Line
            dataKey="p50"
            name={r.median}
            stroke={R.median}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="liquid"
            name={r.liquid}
            stroke={R.liquid}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <ReferenceLine
            x={plan.retired}
            stroke={R.marker}
            strokeDasharray="2 3"
            label={{ value: r.retires, position: "insideTopLeft", fill: R.muted, fontSize: 11 }}
          />
          {later.map((p, k) => (
            <ReferenceLine
              key={p.name}
              x={p.pension_month}
              stroke={R.marker}
              strokeDasharray="2 3"
              label={{
                value: r.pensionOf(p.name),
                position: "insideTopLeft",
                fill: R.muted,
                fontSize: 11,
                dy: 14 * (k + 1),
              }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
