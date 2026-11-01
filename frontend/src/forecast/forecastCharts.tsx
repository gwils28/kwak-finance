/**
 * The forecast's charts (F-FCT-6): the months as Recharts series, the categories as rows in
 * percent of their target. Colours are the `forecast-*` and `progress-*` tokens (spec §7);
 * every chart keeps its legend or labels and a table twin, so no value is reachable only by
 * hovering.
 */
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ErrorBar,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type {
  BacktestOut,
  ForecastAgainstOut,
  ForecastIncomeOut,
  ForecastOut,
  ForecastReliabilityOut,
} from "../api/generated";
import { STATUS_COLOUR, STATUS_ICON, type Status } from "../components/analysis";
import { AXIS, GRID, legendText } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurCompact, formatEurWhole, formatPercent } from "../lib/money";
import { monthLabel } from "../lib/months";

export const C = {
  income: "var(--color-forecast-income)",
  spent: "var(--color-forecast-spent)",
  fixed: "var(--color-forecast-fixed)",
  saved: "var(--color-forecast-saved)",
  rest: "var(--color-forecast-rest)",
  muted: "var(--color-muted)",
  origin: "var(--color-neutral-500)",
  accent: "var(--color-chart-accent)",
};

const STATUS: Record<ForecastAgainstOut["risk"], Status> = {
  likely: "over",
  possible: "watch",
  unlikely: "ok",
};

export function statusOf(a: ForecastAgainstOut): Status {
  return STATUS[a.risk];
}

/** The status's word, for a target (going over) or an objective (falling short). */
export function useRiskWord() {
  const { t } = useI18n();
  const f = t.forecast;
  return (a: ForecastAgainstOut) =>
    a.kind === "savings"
      ? { likely: f.likelyShort, possible: f.mayFallShort, unlikely: f.onTrack }[a.risk]
      : { likely: f.likelyOver, possible: f.mayGoOver, unlikely: f.within }[a.risk];
}

/** A band as words: "—" when there is none yet. */
export function useBandText() {
  const { t } = useI18n();
  return (b: { low: string; high: string; point: string }) =>
    b.low === b.high ? "—" : t.forecast.range(formatEurWhole(b.low), formatEurWhole(b.high));
}

/** A chance to the nearest 5 %, "rare" below 5 % and "nearly always" above 95 % (F-FCT-5). */
export function useChance5() {
  const { t } = useI18n();
  return (chance: string | null) => {
    if (chance === null) return "—";
    const n = Number(chance);
    if (n < 0.05) return t.forecast.rare;
    if (n > 0.95) return t.forecast.nearly;
    return formatPercent(Math.round(n * 20) / 20);
  };
}

/** Every third month, January first: month ticks in the page's language. */
function quarterTicks(months: string[]): string[] {
  return months.filter((m) => Number(m.slice(5)) % 3 === 1);
}

type TipLine = { colour: string; name: string; value: string };

function Tip({ title, lines }: { title: string; lines: TipLine[] }) {
  return (
    <div className="min-w-48 rounded-md border border-border bg-surface p-2 text-xs shadow-md">
      <p className="mb-1 font-semibold">{title}</p>
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
          <span className="tabular font-medium">{line.value}</span>
        </p>
      ))}
    </div>
  );
}

type MonthRow = {
  month: string;
  incomeEntered?: number;
  spentEntered?: number;
  incomeForecast?: number;
  spentForecast?: number;
  incomeBand?: [number, number];
  spentBand?: [number, number];
  fixed: number;
  restEntered?: number;
  restForecast?: number;
  restError?: [number, number];
  restBand?: string;
  incomeBandText?: string;
  spentBandText?: string;
};

export const SHOWN_HISTORY = 12;

function monthRows(f: ForecastOut, bandText: ReturnType<typeof useBandText>): MonthRow[] {
  const past = f.history.slice(-SHOWN_HISTORY);
  const rows: MonthRow[] = past.map((m) => ({
    month: m.month,
    incomeEntered: Number(m.income),
    spentEntered: Number(m.spent),
    fixed: Number(m.fixed),
    restEntered: Number(m.rest),
  }));
  // The dashed forecast starts on the last month entered, so the line runs on.
  const last = rows.at(-1);
  if (last) {
    last.incomeForecast = last.incomeEntered;
    last.spentForecast = last.spentEntered;
  }
  for (const m of f.ahead) {
    const banded = (b: { low: string; high: string }) =>
      b.low === b.high ? undefined : ([Number(b.low), Number(b.high)] as [number, number]);
    rows.push({
      month: m.month,
      incomeForecast: Number(m.income.point),
      spentForecast: Number(m.spent.point),
      incomeBand: banded(m.income),
      spentBand: banded(m.spent),
      incomeBandText: bandText(m.income),
      spentBandText: bandText(m.spent),
      fixed: Number(m.fixed),
      restForecast: Number(m.rest.point),
      restError: [
        Number(m.rest.point) - Number(m.rest.low),
        Number(m.rest.high) - Number(m.rest.point),
      ],
      restBand: bandText(m.rest),
    });
  }
  return rows;
}

/**
 * Income and spent as lines with their bands, the fixed part as bars, and under them, on the
 * same months, the rest as bars, the forecast ones lighter with their band (F-FCT-6).
 */
export function MonthsChart({ forecast }: { forecast: ForecastOut }) {
  const { t } = useI18n();
  const f = t.forecast;
  const bandText = useBandText();
  const data = monthRows(forecast, bandText);
  const ticks = quarterTicks(data.map((r) => r.month));
  const xAxis = {
    dataKey: "month",
    ...AXIS,
    ticks,
    tickFormatter: (m: string) => monthLabel(m),
  };
  const euros = (v: number) => formatEurCompact(v);

  const tooltip = ({ active, label }: { active?: boolean; label?: string | number }) => {
    const row = active ? data.find((r) => r.month === label) : undefined;
    if (!row) return null;
    const ahead = row.restForecast !== undefined;
    const lines: TipLine[] = ahead
      ? [
          {
            colour: C.income,
            name: f.forecastOf(f.income),
            value: `${formatEurWhole(row.incomeForecast ?? 0)} (${row.incomeBandText})`,
          },
          {
            colour: C.spent,
            name: f.forecastOf(f.spent),
            value: `${formatEurWhole(row.spentForecast ?? 0)} (${row.spentBandText})`,
          },
          { colour: C.fixed, name: f.fixed, value: formatEurWhole(row.fixed) },
          {
            colour: C.rest,
            name: f.forecastOf(f.rest),
            value: `${formatEurWhole(row.restForecast ?? 0)} (${row.restBand})`,
          },
        ]
      : [
          { colour: C.income, name: f.income, value: formatEurWhole(row.incomeEntered ?? 0) },
          { colour: C.spent, name: f.spent, value: formatEurWhole(row.spentEntered ?? 0) },
          { colour: C.fixed, name: f.fixed, value: formatEurWhole(row.fixed) },
          { colour: C.rest, name: f.rest, value: formatEurWhole(row.restEntered ?? 0) },
        ];
    return <Tip title={monthLabel(row.month)} lines={lines} />;
  };

  return (
    <div className="flex flex-col gap-1">
      <div className="h-72 sm:h-80" role="img" aria-label={f.monthsChart}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} syncId="forecast" margin={{ top: 8, right: 8, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis {...xAxis} />
            <YAxis {...AXIS} width={64} tickFormatter={euros} />
            <Tooltip content={tooltip} cursor={{ stroke: C.muted, strokeDasharray: "3 3" }} />
            <Legend
              formatter={legendText}
              wrapperStyle={{ fontSize: 12 }}
              itemSorter={null}
              iconType="circle"
            />
            <Bar
              dataKey="fixed"
              name={f.fixed}
              fill={C.fixed}
              fillOpacity={0.6}
              barSize={10}
              isAnimationActive={false}
            />
            {(["income", "spent"] as const).map((key) => (
              <Area
                key={`${key}-band`}
                dataKey={`${key}Band`}
                name={f.band(f[key])}
                stroke="none"
                fill={C[key]}
                fillOpacity={0.18}
                isAnimationActive={false}
                connectNulls={false}
              />
            ))}
            {(["income", "spent"] as const).map((key) => (
              <Line
                key={`${key}-entered`}
                dataKey={`${key}Entered`}
                name={f[key]}
                stroke={C[key]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
            {(["income", "spent"] as const).map((key) => (
              <Line
                key={`${key}-forecast`}
                dataKey={`${key}Forecast`}
                name={f.forecastOf(f[key])}
                stroke={C[key]}
                strokeWidth={2}
                strokeDasharray="6 4"
                dot={false}
                isAnimationActive={false}
              />
            ))}
            <ReferenceLine
              x={forecast.origin}
              stroke={C.origin}
              strokeDasharray="2 3"
              label={{ value: f.origin, position: "insideTopRight", fill: C.muted, fontSize: 11 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <p className="text-sm font-semibold">{f.restOfMonth}</p>
      <div className="h-36" role="img" aria-label={f.restChart}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} syncId="forecast" margin={{ top: 4, right: 8, left: 0 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis {...xAxis} />
            <YAxis {...AXIS} width={64} tickFormatter={euros} />
            <Tooltip content={tooltip} cursor={{ fill: "var(--color-chart-grid)", opacity: 0.4 }} />
            <ReferenceLine y={0} stroke={C.muted} />
            <Bar dataKey="restEntered" name={f.rest} isAnimationActive={false} barSize={10}>
              {data.map((r) => (
                <Cell key={r.month} fill={C.rest} fillOpacity={0.75} />
              ))}
            </Bar>
            <Bar
              dataKey="restForecast"
              name={f.forecastOf(f.rest)}
              isAnimationActive={false}
              barSize={10}
              fill={C.rest}
              fillOpacity={0.25}
              stroke={C.rest}
              strokeOpacity={0.75}
            >
              <ErrorBar dataKey="restError" stroke={C.rest} strokeOpacity={0.5} width={0} />
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const CAP = 160;

function share(value: string, target: string): number {
  const t = Number(target);
  return t ? (100 * Number(value)) / t : 0;
}

/** The axis of a row chart in percent of the target, the target a line at 100 %. */
function PercentScale({ top, step }: { top: number; step: number }) {
  const ticks = [];
  for (let v = 0; v <= top; v += step) ticks.push(v);
  return (
    <div className="relative ml-[40%] h-4 text-[11px] text-muted sm:ml-[35%]" aria-hidden="true">
      {ticks.map((v) => (
        <span
          key={v}
          className="absolute -translate-x-1/2 tabular"
          style={{ left: `${(100 * v) / top}%` }}
        >
          {formatPercent(v / 100)}
        </span>
      ))}
    </div>
  );
}

function Hundred({ top }: { top: number }) {
  return (
    <span
      aria-hidden="true"
      className="absolute inset-y-0 w-0.5 bg-fg"
      style={{ left: `${(100 * 100) / top}%` }}
    />
  );
}

/**
 * A row per category in percent of its target: the forecast a point, the band a bar, the target
 * a line at 100 % (F-FCT-6); the likeliest overrun on top.
 */
export function TargetsChart({ items }: { items: ForecastAgainstOut[] }) {
  const { t } = useI18n();
  const clip = (v: number) => Math.max(0, Math.min(v, CAP));
  const at = (v: number) => `${(100 * clip(v)) / CAP}%`;
  return (
    <div role="img" aria-label={t.forecast.targetsChart} className="flex flex-col gap-1">
      {items.map((a) => {
        const status = statusOf(a);
        const colour = STATUS_COLOUR[status];
        const low = share(a.band.low, a.target);
        const high = share(a.band.high, a.target);
        return (
          <div key={a.category_id} className="flex items-center gap-2 text-sm">
            <span className="w-[40%] truncate sm:w-[35%]">
              <span aria-hidden="true" style={{ color: colour }}>
                {STATUS_ICON[status]}
              </span>{" "}
              {a.name}{" "}
              <span className="text-xs text-muted tabular">
                {formatEurWhole(a.point)} / {formatEurWhole(a.target)}
              </span>
            </span>
            <span className="relative h-6 flex-1">
              <span
                aria-hidden="true"
                className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-chart-grid"
              />
              {a.band.low !== a.band.high && (
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-sm"
                  style={{
                    left: at(low),
                    width: `calc(${at(high)} - ${at(low)})`,
                    background: colour,
                    opacity: 0.3,
                  }}
                />
              )}
              <Hundred top={CAP} />
              <span
                aria-hidden="true"
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface"
                style={{ left: at(share(a.point, a.target)), background: colour }}
              />
            </span>
          </div>
        );
      })}
      <PercentScale top={CAP} step={50} />
    </div>
  );
}

/**
 * A bar per category in percent of its full-year target: to date solid, the forecast to
 * December lighter, the band of the year's total at its end, the target a line at 100 %.
 */
export function YearChart({ items }: { items: ForecastAgainstOut[] }) {
  const { t } = useI18n();
  const top = Math.max(125, ...items.map((a) => share(a.band.high, a.target) + 15));
  const at = (v: number) => `${(100 * Math.max(0, Math.min(v, top))) / top}%`;
  return (
    <div role="img" aria-label={t.forecast.yearChart} className="flex flex-col gap-1">
      {items.map((a) => {
        const status = statusOf(a);
        const colour = a.kind === "savings" ? C.saved : C.spent;
        const toDate = share(a.to_date ?? "0", a.target);
        const point = share(a.point, a.target);
        const banded = a.band.low !== a.band.high;
        return (
          <div key={a.category_id} className="flex items-center gap-2 text-sm">
            <span className="w-[40%] truncate sm:w-[35%]">
              <span aria-hidden="true" style={{ color: STATUS_COLOUR[status] }}>
                {STATUS_ICON[status]}
              </span>{" "}
              {a.name}
            </span>
            <span className="relative h-6 flex-1">
              <span
                aria-hidden="true"
                className="absolute top-1 h-4 rounded-l-sm"
                style={{ left: 0, width: at(toDate), background: colour }}
              />
              <span
                aria-hidden="true"
                className="absolute top-1 h-4 border"
                style={{
                  left: at(toDate),
                  width: `calc(${at(point)} - ${at(toDate)})`,
                  background: colour,
                  opacity: 0.4,
                  borderColor: colour,
                }}
              />
              {banded && (
                <span
                  aria-hidden="true"
                  className="absolute top-1/2 h-px bg-fg"
                  style={{
                    left: at(share(a.band.low, a.target)),
                    width: `calc(${at(share(a.band.high, a.target))} - ${at(share(a.band.low, a.target))})`,
                  }}
                />
              )}
              <Hundred top={top} />
              <span
                className="absolute top-0.5 pl-1 text-xs font-semibold tabular"
                style={{ left: at(Math.max(point, share(a.band.high, a.target))) }}
              >
                {formatPercent(Number(a.point) / Number(a.target))}
              </span>
            </span>
          </div>
        );
      })}
      <PercentScale top={top} step={25} />
    </div>
  );
}

/** This month's income by category, its band a whisker. */
export function IncomeChart({ items }: { items: ForecastIncomeOut[] }) {
  const { t } = useI18n();
  const top = Math.max(1, ...items.map((i) => Number(i.band.high))) * 1.25;
  const at = (v: string) => `${(100 * Math.max(0, Number(v))) / top}%`;
  return (
    <div role="img" aria-label={t.forecast.incomeChart} className="flex flex-col gap-1">
      {items.map((i) => (
        <div key={i.category_id} className="flex items-center gap-2 text-sm">
          <span className="w-[40%] truncate">{i.name}</span>
          <span className="relative h-6 flex-1">
            <span
              aria-hidden="true"
              className="absolute top-1 h-4 rounded-r-sm"
              style={{ left: 0, width: at(i.band.point), background: C.income }}
            />
            {i.band.low !== i.band.high && (
              <span
                aria-hidden="true"
                className="absolute top-1/2 h-px bg-fg"
                style={{
                  left: at(i.band.low),
                  width: `calc(${at(i.band.high)} - ${at(i.band.low)})`,
                }}
              />
            )}
            <span
              className="absolute top-0.5 pl-1 text-xs font-semibold tabular"
              style={{ left: at(i.band.high > i.band.point ? i.band.high : i.band.point) }}
            >
              {formatEurWhole(i.band.point)}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Each category in a contest: how much less its method errs than the 6-month average (left),
 * and how optimistic it was in the past months tested (right of the zero line).
 */
export function ReliabilityChart({ rows, bias }: { rows: ForecastReliabilityOut[]; bias: number }) {
  const { t } = useI18n();
  const f = t.forecast;
  const shown = rows.filter((r) => r.method.contest);
  const side = Math.max(25, ...shown.map((r) => Math.abs(Number(r.optimism ?? 0)) * 100 + 5));
  return (
    <div role="img" aria-label={f.reliabilityChart} className="flex flex-col gap-1 text-sm">
      <div className="flex gap-2 text-xs text-muted">
        <span className="w-[30%]" />
        <span className="flex-[56]">{f.gainAxis}</span>
        <span className="flex-[34] text-center">{f.biasAxis}</span>
      </div>
      {shown.map((r) => {
        const gain = Number(r.versus ?? 0);
        const lean = Number(r.optimism ?? 0) * 100;
        const warn = lean / 100 > bias;
        return (
          <div key={r.category_id} className="flex items-center gap-2">
            <span className="w-[30%] truncate">{r.name}</span>
            <span className="relative h-5 flex-[56]">
              <span
                aria-hidden="true"
                className="absolute top-1 h-3 rounded-r-sm"
                style={{
                  left: 0,
                  width: `${(100 * gain * 100) / 125}%`,
                  background: gain ? C.accent : C.muted,
                }}
              />
              <span
                className={`absolute top-0 pl-1 text-xs ${gain ? "tabular" : ""}`}
                style={{ left: `${(100 * gain * 100) / 125}%` }}
              >
                {gain ? `−${formatPercent(gain)}` : f.same}
              </span>
            </span>
            <span className="relative h-5 flex-[34]">
              <span aria-hidden="true" className="absolute inset-y-0 left-1/2 w-px bg-fg" />
              <span
                aria-hidden="true"
                className="absolute top-1 h-3"
                style={{
                  left: lean >= 0 ? "50%" : `${50 + (50 * lean) / side}%`,
                  width: `${(50 * Math.abs(lean)) / side}%`,
                  background: warn ? STATUS_COLOUR.watch : C.muted,
                }}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}

/** At each cut, income and spent as entered and as forecast one month ahead. */
export function BacktestChart({ series }: { series: BacktestOut[] }) {
  const { t } = useI18n();
  const f = t.forecast;
  const months = [...new Set(series.flatMap((s) => s.points.map((p) => p.month)))].sort();
  const data = months.map((month) => {
    const row: Record<string, number | string> = { month };
    for (const s of series) {
      const p = s.points.find((x) => x.month === month);
      if (p) {
        row[`${s.name}Entered`] = Number(p.entered);
        row[`${s.name}Forecast`] = Number(p.forecast);
      }
    }
    return row;
  });
  return (
    <div className="h-72" role="img" aria-label={f.backtestChart}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="month"
            {...AXIS}
            ticks={quarterTicks(months)}
            tickFormatter={(m: string) => monthLabel(m)}
          />
          <YAxis {...AXIS} width={64} tickFormatter={(v: number) => formatEurCompact(v)} />
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              color: "var(--color-fg)",
              fontSize: 12,
            }}
            labelFormatter={(m: unknown) => monthLabel(String(m))}
            formatter={(v: unknown) => formatEurWhole(Number(v))}
          />
          <Legend formatter={legendText} wrapperStyle={{ fontSize: 12 }} iconType="circle" />
          {series.map((s) => (
            <Line
              key={`${s.name}-entered`}
              dataKey={`${s.name}Entered`}
              name={f.entered(f[s.name])}
              stroke={C[s.name]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
          {series.map((s) => (
            <Line
              key={`${s.name}-forecast`}
              dataKey={`${s.name}Forecast`}
              name={f.oneAhead(f[s.name])}
              stroke={C[s.name]}
              strokeWidth={1.5}
              strokeDasharray="6 4"
              dot={{ r: 2 }}
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
