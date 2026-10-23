/**
 * The goals seen together (spec §4.12): their required efforts against the capacity, their
 * dates on a timeline and their status month by month. A goal keeps its tier's colour; goals of
 * one tier are told apart by their label and a hatch, never by a new hue. Every chart has its
 * table.
 */
import { useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  ForwardOut,
  GoalAnalysisOut,
  RiskPointOut,
  StatusRowOut,
  TimelineOut,
  Zone,
} from "../api/generated";
import { AXIS, Card, DataTable, GRID, legendText, TOOLTIP } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent, formatRateSigned } from "../lib/money";
import { monthLabel, shiftMonth } from "../lib/months";
import { StatusChip, tierColour } from "./shared";

const FG = "var(--color-fg)";
const SURFACE = "var(--color-surface)";
const OVER = "var(--color-progress-over)";

const index = (month: string) => {
  const [y, m] = month.split("-").map(Number) as [number, number];
  return y * 12 + m - 1;
};

/** Which bands wear a hatch: every other goal within one tier. */
function hatched<T extends { tier: string }>(items: T[]): boolean[] {
  const seen = new Map<string, number>();
  return items.map((item) => {
    const n = seen.get(item.tier) ?? 0;
    seen.set(item.tier, n + 1);
    return n % 2 === 1;
  });
}

function Hatch({ id, colour }: { id: string; colour: string }) {
  return (
    <pattern
      id={id}
      width="8"
      height="8"
      patternUnits="userSpaceOnUse"
      patternTransform="rotate(45)"
    >
      <rect width="8" height="8" fill={colour} />
      <line x1="0" y1="0" x2="0" y2="8" stroke={SURFACE} strokeWidth="3" strokeOpacity="0.6" />
    </pattern>
  );
}

export const HORIZONS = [12, 24, 36, 48, 60];

/** How many months a band lasts: a goal due in the reference month still takes that one, as
 * the totals count it. */
const lasts = (b: { months: number }) => Math.max(1, b.months);

const SHORT_CAPACITY = 3;
const FULL_YEAR = 12;

/** F-ANA-2: what each goal needs every month, stacked, against the household's capacity. */
export function Forward({
  data,
  horizon,
  onHorizon,
  scoped,
}: {
  data: GoalAnalysisOut;
  horizon: number;
  onHorizon: (months: number) => void;
  scoped: boolean;
}) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const id = useId();
  const forward: ForwardOut = data.forward;
  const capacity = Number(data.capacity);
  const hatch = hatched(forward.bands);
  const rows = forward.months.map((month, k) => ({
    month,
    ...Object.fromEntries(
      forward.bands.map((b) => [b.goal_id, k < lasts(b) ? Number(b.amount) : 0]),
    ),
  }));
  const over = forward.months.filter((_, k) => Number(forward.totals[k]) > capacity);
  const names = new Map(forward.bands.map((b) => [b.goal_id, b.name]));
  const order = new Map(forward.bands.map((b, i) => [b.goal_id, i]));
  const subtitle = [
    a.forwardHelp,
    a.capacityIs(
      formatEurWhole(data.capacity),
      data.capacity_set ? a.capacitySet : a.capacityMeasured(data.capacity_months),
    ),
    ...(!data.capacity_set && data.capacity_months < FULL_YEAR ? [a.irregular] : []),
    ...(scoped ? [a.householdCapacity] : []),
  ].join(" ");
  return (
    <Card
      title={a.forward}
      subtitle={subtitle}
      aside={
        <label htmlFor={id} className="flex flex-col gap-1 text-sm font-medium">
          {a.horizon}
          <select
            id={id}
            className="rounded-md border border-border bg-surface px-3 py-2"
            value={horizon}
            onChange={(e) => onHorizon(Number(e.target.value))}
          >
            {HORIZONS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {!data.capacity_set && data.capacity_months < SHORT_CAPACITY ? (
        <p className="text-sm text-muted">{a.capacityShort(data.capacity_months)}</p>
      ) : forward.bands.length === 0 ? (
        <p className="text-sm text-muted">{a.noBand}</p>
      ) : (
        <>
          <p role="status" className="text-sm font-medium">
            {a.over(forward.over, formatEurWhole(forward.peak))}
          </p>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 8 }}>
                <defs>
                  {forward.bands.map((b, i) =>
                    hatch[i] ? (
                      <Hatch key={b.goal_id} id={`${id}-${i}`} colour={tierColour(b.tier)} />
                    ) : null,
                  )}
                </defs>
                <CartesianGrid vertical={false} stroke={GRID} />
                <XAxis dataKey="month" tickFormatter={monthLabel} {...AXIS} />
                <YAxis tickFormatter={(v: number) => formatEurWhole(v)} width={84} {...AXIS} />
                <Tooltip
                  {...TOOLTIP}
                  itemStyle={{ color: FG }}
                  labelFormatter={(m) => monthLabel(String(m))}
                  itemSorter={(item) => order.get(String(item.dataKey)) ?? order.size}
                  formatter={(v, name) => [
                    formatEurWhole(Number(v)),
                    names.get(String(name)) ?? String(name),
                  ]}
                />
                <Legend
                  itemSorter={null}
                  formatter={(goal: string) => legendText(names.get(goal) ?? goal)}
                  wrapperStyle={{ fontSize: 12 }}
                />
                {forward.bands.map((b, i) => (
                  <Area
                    key={b.goal_id}
                    dataKey={b.goal_id}
                    stackId="effort"
                    type="stepAfter"
                    // The legend draws its key in the stroke's colour.
                    stroke={tierColour(b.tier)}
                    strokeWidth={1}
                    fill={hatch[i] ? `url(#${id}-${i})` : tierColour(b.tier)}
                    fillOpacity={1}
                    isAnimationActive={false}
                  />
                ))}
                {over.length > 0 && (
                  // Drawn over the bands, up to the month after the last one over: a step
                  // covers its whole month.
                  <ReferenceArea
                    x1={over[0]}
                    x2={
                      forward.months[forward.months.indexOf(over.at(-1) ?? "") + 1] ?? over.at(-1)
                    }
                    fill={OVER}
                    fillOpacity={0.25}
                    label={{ value: a.overArea, position: "insideTopLeft", fill: FG, fontSize: 12 }}
                  />
                )}
                <ReferenceLine
                  y={capacity}
                  stroke={FG}
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  label={{ value: a.capacity, position: "insideTopRight", fill: FG, fontSize: 12 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      <DataTable
        label={a.forwardTable}
        head={[a.month, ...forward.bands.map((b) => b.name), a.total, a.capacity]}
        rows={forward.months.map((month, k) => [
          monthLabel(month),
          ...forward.bands.map((b) => formatEurWhole(k < lasts(b) ? b.amount : "0")),
          formatEurWhole(forward.totals[k] ?? "0"),
          formatEurWhole(data.capacity),
        ])}
      />
    </Card>
  );
}

const W = 960;
const ROW = 32;
const LEFT = 180;
const RIGHT = 24;
const TOP = 28;
const MAX_MONTHS = 120;

/** F-ANA-3: each goal from its start to its deadline, where it lands at its pace and at the
 * plan. */
export function Timeline({ data }: { data: GoalAnalysisOut }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const id = useId();
  const bars: TimelineOut[] = data.timeline;
  if (bars.length === 0) return null;
  const reference = data.reference ?? data.month;
  // From the earliest start, or the reference month when every goal began after it.
  const first = [reference, ...bars.map((b) => b.start)].reduce((x, y) =>
    index(y) < index(x) ? y : x,
  );
  const known = bars.flatMap((b) => [b.deadline, b.estimated, b.at_plan]).filter(Boolean);
  const latest = [shiftMonth(reference, 12), ...(known as string[])].reduce((x, y) =>
    index(y) > index(x) ? y : x,
  );
  // A date beyond ten years from the reference shows as an arrow at the edge.
  const cap = shiftMonth(reference, MAX_MONTHS);
  const end = index(latest) > index(cap) ? cap : latest;
  const span = Math.max(1, index(end) - index(first));
  const H = TOP + ROW * bars.length + 8;
  const x = (month: string) =>
    LEFT + ((W - LEFT - RIGHT) * Math.min(span, index(month) - index(first))) / span;
  const beyond = (month: string) => index(month) > index(end);
  const every = Math.max(1, Math.ceil(span / 8));
  const ticks = Array.from({ length: Math.floor(span / every) + 1 }, (_, i) =>
    shiftMonth(first, i * every),
  );
  const hatch = hatched(bars);
  const date = (month: string | null, fallback: string) => (month ? monthLabel(month) : fallback);
  return (
    <Card title={a.timeline} subtitle={a.timelineHelp}>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full min-w-[640px]"
          role="img"
          aria-label={a.timelineLabel}
        >
          <defs>
            {bars.map((b, i) =>
              hatch[i] ? (
                <Hatch key={b.goal_id} id={`${id}-${i}`} colour={tierColour(b.tier)} />
              ) : null,
            )}
          </defs>
          {ticks.map((m) => (
            <g key={m}>
              <line x1={x(m)} x2={x(m)} y1={TOP - 6} y2={H} stroke={GRID} />
              <text
                x={x(m)}
                y={14}
                // Kept inside the frame at both ends.
                textAnchor={x(m) < LEFT + 40 ? "start" : x(m) > W - RIGHT - 40 ? "end" : "middle"}
                className="fill-muted text-[11px]"
              >
                {monthLabel(m)}
              </text>
            </g>
          ))}
          <line
            x1={x(reference)}
            x2={x(reference)}
            y1={TOP - 6}
            y2={H}
            stroke={FG}
            strokeWidth={1.5}
            strokeDasharray="3 3"
          />
          {bars.map((b, i) => {
            const y = TOP + ROW * i;
            const mid = y + ROW / 2 - 2;
            const to = b.deadline ?? end;
            return (
              <g key={b.goal_id}>
                <text x={LEFT - 8} y={mid + 4} textAnchor="end" className="fill-fg text-[12px]">
                  {b.name.length > 24 ? `${b.name.slice(0, 23)}…` : b.name}
                </text>
                <rect
                  x={x(b.start)}
                  y={y + 6}
                  width={Math.max(2, x(to) - x(b.start))}
                  height={ROW - 16}
                  rx={4}
                  fill={hatch[i] ? `url(#${id}-${i})` : tierColour(b.tier)}
                  fillOpacity={b.deadline ? 1 : 0.45}
                />
                {b.estimated && !beyond(b.estimated) && (
                  <circle
                    cx={x(b.estimated)}
                    cy={mid}
                    r={6}
                    fill={b.enough_history ? FG : SURFACE}
                    stroke={FG}
                    strokeWidth={2}
                    strokeDasharray={b.enough_history ? undefined : "2 2"}
                  />
                )}
                {((b.estimated && beyond(b.estimated)) ||
                  (b.at_plan && beyond(b.at_plan)) ||
                  (b.deadline && beyond(b.deadline)) ||
                  b.never) && (
                  <text
                    x={W - RIGHT + 4}
                    y={mid + 5}
                    textAnchor="end"
                    className="fill-fg text-[14px]"
                  >
                    <title>{a.beyond}</title>→
                  </text>
                )}
                {b.at_plan && !beyond(b.at_plan) && (
                  <path
                    d={`M ${x(b.at_plan)} ${mid - 7} l 7 7 l -7 7 l -7 -7 z`}
                    fill={SURFACE}
                    stroke={FG}
                    strokeWidth={2}
                  />
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <DataTable
        label={a.timelineTable}
        head={[a.goal, a.start, a.deadline, a.atPace, a.atPlan]}
        rows={bars.map((b) => [
          b.name,
          monthLabel(b.start),
          date(b.deadline, a.noDeadline),
          b.never
            ? a.never
            : `${date(b.estimated, "—")}${b.enough_history ? "" : ` (${a.notEnough})`}`,
          date(b.at_plan, "—"),
        ])}
      />
    </Card>
  );
}

/** F-ANA-6: each goal's status at the end of each month; the grid is its own table. */
export function StatusGrid({ data }: { data: GoalAnalysisOut }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const rows: StatusRowOut[] = data.statuses;
  const months = [...new Set(rows.flatMap((r) => r.months.map((m) => m.month)))].sort(
    (x, y) => index(x) - index(y),
  );
  if (rows.length === 0 || months.length === 0) return null;
  return (
    <Card title={a.statuses} subtitle={a.statusesHelp}>
      <div className="overflow-x-auto">
        <table aria-label={a.statusesTable} className="w-full text-sm">
          <thead className="text-left text-muted">
            <tr>
              <th className="sticky left-0 bg-surface py-1 pr-3 font-medium">{a.goal}</th>
              {months.map((m) => (
                <th key={m} className="whitespace-nowrap px-1 py-1 text-center font-medium">
                  {monthLabel(m)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const by = new Map(row.months.map((m) => [m.month, m.status]));
              return (
                <tr key={row.goal_id} className="border-t border-border">
                  <th
                    scope="row"
                    className="sticky left-0 whitespace-nowrap bg-surface py-1 pr-3 text-left font-normal"
                  >
                    <span
                      aria-hidden="true"
                      className="mr-2 inline-block size-2.5 rounded-full align-middle"
                      style={{ background: tierColour(row.tier) }}
                    />
                    {row.name}
                  </th>
                  {months.map((m) => {
                    const status = by.get(m);
                    return (
                      <td key={m} className="px-1 py-1 text-center">
                        {status ? <StatusChip status={status} /> : null}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const RISK_H = 300;
const RISK_PAD = { left: 64, right: 40, top: 24, bottom: 48 };
/** Points keep clear of the axes and their labels. */
const INSET = 16;
const RISK_MONTHS = 120;
const AMBER = "var(--color-secondary-500)";

/** Each zone's ring: its colour and its dash, so colour is never the only cue. */
const RING: Record<Zone, { colour: string; dash?: string } | null> = {
  none: null,
  red_short: { colour: OVER },
  amber_glide: { colour: AMBER, dash: "6 3" },
  red_eroding: { colour: OVER },
};

/** F-ANA-4: each funded goal by the months left to its deadline and the weighted volatility of
 * its lines, over the zones; goals without a deadline are listed under it. */
export function RiskChart({ data }: { data: GoalAnalysisOut }) {
  const { t } = useI18n();
  const a = t.goalAnalysis;
  const points: RiskPointOut[] = data.risk;
  if (points.length === 0) return null;
  const dated = points.filter((p) => p.months_left !== null);
  const undated = points.filter((p) => p.months_left === null);
  const top = Math.max(0.3, ...dated.map((p) => Number(p.volatility) * 1.1));
  const x = (months: number) =>
    RISK_PAD.left +
    INSET +
    ((W - RISK_PAD.left - RISK_PAD.right - 2 * INSET) *
      Math.min(RISK_MONTHS, Math.max(0, months))) /
      RISK_MONTHS;
  const y = (sigma: number) =>
    RISK_PAD.top + (RISK_H - RISK_PAD.top - RISK_PAD.bottom - INSET) * (1 - sigma / top);
  const bottom = RISK_H - RISK_PAD.bottom;
  const left = RISK_PAD.left;
  const right = W - RISK_PAD.right;
  const xTicks = [0, 12, 24, 36, 48, 60, 72, 84, 96, 108, 120];
  const yTicks = [0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.6].filter((v) => v <= top);
  const percent = (value: string | null) => (value === null ? "—" : formatPercent(value));
  return (
    <Card title={a.risk} subtitle={a.riskHelp(formatPercent(data.inflation))}>
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${W} ${RISK_H}`}
          className="w-full min-w-[640px]"
          role="img"
          aria-label={a.riskLabel}
        >
          {/* The zones (F-ANA-4): near and volatile, the glide path, far and eroding. */}
          <rect
            x={left}
            y={RISK_PAD.top}
            width={x(24) - left}
            height={y(0.05) - RISK_PAD.top}
            fill={OVER}
            fillOpacity={0.2}
          />
          <rect
            x={x(24)}
            y={RISK_PAD.top}
            width={x(60) - x(24)}
            height={bottom - RISK_PAD.top}
            fill={AMBER}
            fillOpacity={0.14}
          />
          <rect
            x={x(96)}
            y={RISK_PAD.top}
            width={right - x(96)}
            height={bottom - RISK_PAD.top}
            fill={OVER}
            fillOpacity={0.12}
          />
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={left} x2={right} y1={y(v)} y2={y(v)} stroke={GRID} />
              <text
                x={RISK_PAD.left - 8}
                y={y(v) + 4}
                textAnchor="end"
                className="tabular fill-muted text-[11px]"
              >
                {formatPercent(v)}
              </text>
            </g>
          ))}
          {xTicks.map((m) => (
            <text
              key={m}
              x={x(m)}
              y={bottom + 18}
              textAnchor={m === 0 ? "start" : m === RISK_MONTHS ? "end" : "middle"}
              className="tabular fill-muted text-[11px]"
            >
              {m === RISK_MONTHS ? `${m}+` : m}
            </text>
          ))}
          <text x={x(60)} y={RISK_H - 4} textAnchor="middle" className="fill-muted text-[11px]">
            {a.monthsAxis}
          </text>
          <text x={RISK_PAD.left} y={10} className="fill-muted text-[11px]">
            {a.volatilityAxis}
          </text>
          {dated.map((p) => {
            const cx = x(p.months_left ?? 0);
            const cy = y(Number(p.volatility));
            const ring = p.zone ? RING[p.zone] : null;
            return (
              <g key={p.goal_id}>
                {ring && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={11}
                    fill="none"
                    stroke={ring.colour}
                    strokeWidth={3}
                    strokeDasharray={ring.dash}
                  />
                )}
                {p.losing && (
                  <circle
                    cx={cx}
                    cy={cy}
                    r={15}
                    fill="none"
                    stroke={FG}
                    strokeWidth={1.5}
                    strokeDasharray="1 3"
                  />
                )}
                <circle
                  cx={cx}
                  cy={cy}
                  r={7}
                  fill={tierColour(p.tier)}
                  stroke={FG}
                  strokeWidth={1}
                />
                <text
                  x={cx + (cx > W - 160 ? -14 : 14)}
                  y={cy + 4}
                  textAnchor={cx > W - 160 ? "end" : "start"}
                  className="fill-fg text-[12px]"
                >
                  {p.name.length > 24 ? `${p.name.slice(0, 23)}…` : p.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      {undated.length > 0 && (
        <p className="text-sm text-muted">
          {a.noDeadlineGoals}{" "}
          {undated
            .map(
              (p) =>
                `${p.name} (${a.volatility.toLowerCase()} ${percent(p.volatility)}, ${a.realReturn.toLowerCase()} ${formatRateSigned(p.real_return)})`,
            )
            .join(" · ")}
        </p>
      )}
      <DataTable
        label={a.riskTable}
        head={[a.goal, a.monthsLeft, a.volatility, a.realReturn, a.riskyShare, a.loss, a.zoneLabel]}
        rows={points.map((p) => [
          p.name,
          p.months_left === null ? a.noDeadline : String(p.months_left),
          percent(p.volatility),
          formatRateSigned(p.real_return),
          percent(p.risky_share),
          p.loss === null ? "—" : formatRateSigned(p.loss),
          [p.zone && p.zone !== "none" ? a.zone[p.zone] : null, p.losing ? a.losing : null]
            .filter(Boolean)
            .join(", ") || "—",
        ])}
      />
    </Card>
  );
}
