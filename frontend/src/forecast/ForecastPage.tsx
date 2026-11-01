/**
 * The cash-flow forecast (F-FCT-6): the answer first in tiles, then one chart per question
 * (the months, the targets, the income and the objectives, the year), and folded how reliable
 * it is (what each forecast rests on, the back-test, the limits).
 */
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  type ForecastAgainstOut,
  type ForecastOut,
  type ForecastReliabilityOut,
  type ForecastScoreOut,
  getForecast,
} from "../api/generated";
import { Callout, Chip, Fold, Jump, Tile, Tiles, WordTable } from "../components/analysis";
import { ErrorAlert } from "../components/ui";
import { Card, DataTable } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatEurWhole, formatPercent, formatRatio } from "../lib/money";
import { monthLabel } from "../lib/months";
import {
  BacktestChart,
  IncomeChart,
  MonthsChart,
  ReliabilityChart,
  statusOf,
  TargetsChart,
  useBandText,
  useChance5,
  useRiskWord,
  YearChart,
} from "./forecastCharts";

export const FORECAST_KEY = ["forecast"];
const HORIZON = 12;

export function ForecastPage() {
  const { t } = useI18n();
  const f = t.forecast;
  const query = useQuery({
    queryKey: FORECAST_KEY,
    queryFn: async () => (await getForecast({ throwOnError: true })).data,
    staleTime: 5 * 60_000,
  });
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-black tracking-tight">{f.title}</h1>
      <p className="max-w-3xl text-muted">{f.intro}</p>
      {query.isPending && (
        <p role="status" className="text-muted">
          {f.loading}
        </p>
      )}
      {query.isError && <ErrorAlert message={t.errors.generic} />}
      {query.data && !query.data.forecast && (
        <p className="rounded-lg border border-border bg-surface p-4">
          {f.notEnough(query.data.complete_months, query.data.needed)}
        </p>
      )}
      {query.data?.forecast && <Forecast forecast={query.data.forecast} />}
    </div>
  );
}

function Forecast({ forecast: r }: { forecast: ForecastOut }) {
  const { t } = useI18n();
  const f = t.forecast;
  const bandText = useBandText();
  const first = monthLabel(r.ahead[0]?.month ?? r.origin);
  const last = monthLabel(r.ahead.at(-1)?.month ?? r.origin);
  return (
    <div className="flex flex-col gap-4">
      <Jump
        label={f.sections}
        links={[
          ["fct-month", f.jumpMonth],
          ["fct-months", f.jumpMonths],
          ["fct-targets", f.jumpTargets],
          ["fct-year", f.jumpYear],
          ["fct-reliable", f.jumpReliable],
        ]}
      />
      {r.rest_above !== null && <Callout>{f.restWarning(formatEurWhole(r.rest_above))}</Callout>}
      <Summary r={r} first={first} last={last} />

      <div className="grid gap-4 lg:grid-cols-3">
        <section id="fct-months" className="scroll-mt-4 lg:col-span-3">
          <Card title={f.monthsTitle} subtitle={f.monthsLede}>
            <MonthsChart forecast={r} />
            {r.band.none && <p className="text-sm text-muted">{f.noBand}</p>}
            {r.band.widened_from && (
              <p className="text-sm text-muted">{f.widened(monthLabel(r.band.widened_from))}</p>
            )}
            <DataTable
              label={f.monthsTitle}
              head={[f.colMonth, f.income, f.spent, f.saved, f.rest]}
              rows={[
                ...r.history.map((m) => [
                  monthLabel(m.month),
                  formatEurWhole(m.income),
                  formatEurWhole(m.spent),
                  formatEurWhole(m.saved),
                  formatEurWhole(m.rest),
                ]),
                ...r.ahead.map((m) => [
                  `${monthLabel(m.month)} *`,
                  ...[m.income, m.spent, m.saved, m.rest].map((b) => {
                    const band = bandText(b);
                    return formatEurWhole(b.point) + (band === "—" ? "" : ` (${band})`);
                  }),
                ]),
              ]}
            />
          </Card>
        </section>

        <section id="fct-targets" className="scroll-mt-4 lg:col-span-2">
          <Card
            title={f.targetsTitle}
            subtitle={r.targets.length ? `${f.targetsIntro(first)} ${f.targetsLede}` : undefined}
          >
            {r.targets.length === 0 ? (
              <p className="text-sm text-muted">{f.noTarget}</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-1">
                  <Chip status="over">{f.likelyOver}</Chip>
                  <Chip status="watch">{f.mayGoOver}</Chip>
                  <Chip status="ok">{f.within}</Chip>
                </div>
                <TargetsChart items={r.targets} />
                <AgainstTable items={r.targets} objective={false} />
              </>
            )}
          </Card>
        </section>

        <IncomeCard r={r} month={first} />

        {r.year_targets.length > 0 && (
          <section id="fct-year" className="scroll-mt-4 lg:col-span-3">
            <Card
              title={f.yearTitle(r.year)}
              subtitle={`${f.yearIntro(monthLabel(r.origin))} ${f.yearLede}`}
            >
              <div className="flex flex-wrap gap-3 text-xs text-muted">
                <Swatch colour="var(--color-forecast-spent)">
                  {f.toOrigin(monthLabel(r.origin))}
                </Swatch>
                <Swatch colour="var(--color-forecast-spent)" light>
                  {f.colToDecember}
                </Swatch>
              </div>
              <YearChart items={r.year_targets} />
              <YearTable items={r.year_targets} year={r.year} />
            </Card>
          </section>
        )}
      </div>

      <Fold id="fct-reliable" title={f.reliableTitle} hint={f.reliableHint}>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title={f.restsTitle} subtitle={f.restsIntro}>
            <ReliabilityChart rows={r.reliability} bias={Number(r.bias_limit)} />
            <RestsOnTable rows={r.reliability} />
          </Card>
          <Card title={f.backtestTitle} subtitle={f.backtestIntro}>
            <BacktestChart series={r.backtest} />
            <ScoresTable scores={r.scores} />
            <DataTable
              label={f.backtestTitle}
              head={[f.colMonth, f.colTotal, f.colEntered, f.colOneAhead]}
              rows={r.backtest.flatMap((s) =>
                s.points.map((p) => [
                  monthLabel(p.month),
                  f[s.name],
                  formatEurWhole(p.entered),
                  formatEurWhole(p.forecast),
                ]),
              )}
            />
          </Card>
        </div>
        <div>
          <h3 className="font-semibold">{f.limitsTitle}</h3>
          <ul className="list-disc pl-5 text-sm text-muted">
            {f.limits.map((limit) => (
              <li key={limit}>{limit}</li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted">
            {f.engine(
              r.engine.cuts,
              r.engine.months,
              String(r.engine.seed),
              String(r.engine.version),
            )}{" "}
            {Object.keys(r.engine.models).length
              ? f.foundationModels(
                  Object.entries(r.engine.models)
                    .map(([name, revision]) => `${f.modelNames[name] ?? name} (${revision})`)
                    .join(", "),
                )
              : f.noFoundationModels}
          </p>
        </div>
      </Fold>
      <p className="max-w-3xl text-sm text-muted">{f.disclaimer}</p>
    </div>
  );
}

function Swatch({
  colour,
  light = false,
  children,
}: {
  colour: string;
  light?: boolean;
  children: ReactNode;
}) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        aria-hidden="true"
        className="inline-block h-2.5 w-4 rounded-sm border"
        style={{ background: colour, opacity: light ? 0.4 : 1, borderColor: colour }}
      />
      {children}
    </span>
  );
}

function Summary({ r, first, last }: { r: ForecastOut; first: string; last: string }) {
  const { t } = useI18n();
  const f = t.forecast;
  const o = r.totals;
  const values = [
    first,
    last,
    formatEurWhole(o.income.point),
    formatEurWhole(o.spent.point),
    formatEurWhole(o.saved.point),
    formatEurWhole(o.rest.point),
  ] as const;
  const sentence = o.banded
    ? f.summary(...values, formatEurWhole(o.rest.low), formatEurWhole(o.rest.high))
    : f.summaryNoBand(...values);
  const m = r.month;
  const above =
    Number(m.expected.high) > Number(m.expected.point) &&
    Number(m.entered) > Number(m.expected.high);
  const current = above
    ? f.nowAbove(formatEurWhole(m.entered), first, formatEurWhole(m.expected.high))
    : f.now(formatEurWhole(m.entered), first, formatEurWhole(m.expected.point));
  const share = Number(m.expected.point) > 0 ? Number(m.entered) / Number(m.expected.point) : 0;
  const perMonth = (total: string) => f.perMonth(formatEurWhole(Number(total) / HORIZON));
  return (
    <Tiles>
      <Tile
        label={f.tileRest(first, last)}
        value={formatEurWhole(o.rest.point)}
        note={sentence}
        wide
      />
      <Tile
        id="fct-month"
        label={f.tileMonth(first)}
        value={formatEurWhole(m.entered)}
        note={current}
      >
        <Pace share={share} gone={m.elapsed === null ? null : Number(m.elapsed)} />
      </Tile>
      <RiskTile label={f.tileTargets} items={r.targets} />
      <RiskTile label={f.tileYear(r.year)} items={r.year_targets} names />
      <Tile
        label={f.tileIncome}
        value={formatEurWhole(o.income.point)}
        note={perMonth(o.income.point)}
      />
      <Tile
        label={f.tileSpent}
        value={formatEurWhole(o.spent.point)}
        note={perMonth(o.spent.point)}
      />
      <Tile
        label={f.tileSaved}
        value={formatEurWhole(o.saved.point)}
        note={perMonth(o.saved.point)}
      />
    </Tiles>
  );
}

/** The month's spending against its forecast, a tick where the month's days have got to. */
function Pace({ share, gone }: { share: number; gone: number | null }) {
  const { t } = useI18n();
  const filled = Math.min(share, 1) * 100;
  const label = t.forecast.paceLabel(
    formatPercent(share),
    gone === null ? "—" : formatPercent(gone),
  );
  return (
    <div className="relative h-2 rounded-full bg-chart-grid">
      <meter className="sr-only" min={0} max={1} value={Math.min(share, 1)} aria-label={label} />
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 rounded-full"
        style={{ width: `${filled}%`, background: "var(--color-forecast-spent)" }}
      />
      {gone !== null && (
        <span
          aria-hidden="true"
          className="absolute -inset-y-1 w-0.5 bg-fg"
          style={{ left: `${gone * 100}%` }}
        />
      )}
    </div>
  );
}

/** How many targets are at risk, a chip per level; with no target, says so. */
function RiskTile({
  label,
  items,
  names = false,
}: {
  label: string;
  items: ForecastAgainstOut[];
  names?: boolean;
}) {
  const { t } = useI18n();
  const f = t.forecast;
  if (items.length === 0) return <Tile label={label} value="—" note={f.noTarget} />;
  const likely = items.filter((a) => a.risk === "likely");
  const possible = items.filter((a) => a.risk === "possible");
  const atRisk = likely.length + possible.length;
  const chips = atRisk ? (
    <>
      {likely.length > 0 && <Chip status="over">{f.countOver(likely.length)}</Chip>}
      {possible.length > 0 && <Chip status="watch">{f.countWatch(possible.length)}</Chip>}
    </>
  ) : (
    <Chip status="ok">{f.allWithin}</Chip>
  );
  return (
    <Tile
      label={label}
      value={f.atRisk(atRisk, items.length)}
      chips={chips}
      note={names && likely.length ? likely.map((a) => a.name).join(", ") : undefined}
    />
  );
}

function AgainstTable({ items, objective }: { items: ForecastAgainstOut[]; objective: boolean }) {
  const { t } = useI18n();
  const f = t.forecast;
  const bandText = useBandText();
  const chance = useChance5();
  const word = useRiskWord();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">{t.common.showData}</summary>
      <div className="mt-2">
        <WordTable
          label={objective ? f.savingsTitle : f.targetsTitle}
          head={[
            f.colCategory,
            f.colForecast,
            f.colBand,
            objective ? f.colObjective : f.colTarget,
            f.colOdds,
            f.colStatus,
          ]}
          rows={items.map((a) => [
            a.name,
            formatEurWhole(a.point),
            bandText(a.band),
            formatEurWhole(a.target),
            chance(a.chance),
            word(a),
          ])}
          worded={[4, 5]}
        />
      </div>
    </details>
  );
}

function YearTable({ items, year }: { items: ForecastAgainstOut[]; year: number }) {
  const { t } = useI18n();
  const f = t.forecast;
  const bandText = useBandText();
  const chance = useChance5();
  const word = useRiskWord();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">{t.common.showData}</summary>
      <div className="mt-2">
        <WordTable
          label={f.yearTitle(year)}
          head={[
            f.colCategory,
            f.colToDate,
            f.colToDecember,
            f.colYear,
            f.colBand,
            f.colYearTarget,
            f.colOdds,
            f.colStatus,
          ]}
          rows={items.map((a) => [
            a.name,
            formatEurWhole(a.to_date ?? "0"),
            formatEurWhole(Number(a.point) - Number(a.to_date ?? 0)),
            formatEurWhole(a.point),
            bandText(a.band),
            formatEurWhole(a.target),
            chance(a.chance),
            word(a),
          ])}
          worded={[6, 7]}
        />
      </div>
    </details>
  );
}

/** This month's income by category, then the savings objectives as chips. */
function IncomeCard({ r, month }: { r: ForecastOut; month: string }) {
  const { t } = useI18n();
  const f = t.forecast;
  const bandText = useBandText();
  const word = useRiskWord();
  if (r.income.length === 0 && r.objectives.length === 0) return null;
  return (
    <section className="lg:col-span-1">
      <Card title={f.incomeTitle} subtitle={f.incomeLede(month)}>
        {r.income.length > 0 && (
          <>
            <IncomeChart items={r.income} />
            <DataTable
              label={f.incomeTitle}
              head={[f.colCategory, f.colForecast, f.colBand]}
              rows={r.income.map((i) => [i.name, formatEurWhole(i.band.point), bandText(i.band)])}
            />
          </>
        )}
        {r.objectives.length > 0 && (
          <>
            <h3 className="mt-2 font-semibold">{f.savingsTitle}</h3>
            <p className="text-sm text-muted">{f.savingsIntro(month)}</p>
            <div className="flex flex-wrap gap-1">
              {r.objectives.map((a) => (
                <Chip key={a.category_id} status={statusOf(a)}>
                  {f.objectiveChip(
                    a.name,
                    formatEurWhole(a.point),
                    formatEurWhole(a.target),
                    word(a),
                  )}
                </Chip>
              ))}
            </div>
            <AgainstTable items={r.objectives} objective />
          </>
        )}
      </Card>
    </section>
  );
}

/** A bias (entered less forecast, over what was entered) in words, for its kind. */
function useBiasText() {
  const { t } = useI18n();
  const f = t.forecast;
  return (bias: string | null, kind: "expense" | "income" | "savings") => {
    if (bias === null) return "—";
    const n = Number(bias);
    if (Math.abs(n) < 0.01) return f.biasNone;
    const words = f.bias[kind];
    return (n > 0 ? words.less : words.more)(formatPercent(Math.abs(n)));
  };
}

function useMethodText() {
  const { t } = useI18n();
  const f = t.forecast;
  const biasText = useBiasText();
  return (r: ForecastReliabilityOut) => {
    const m = r.method;
    if (m.model === null) return f.noMethod;
    let words = f.models[m.model] ?? m.model;
    if (!m.contest) return f.noContest(words);
    if (m.features.length) {
      words = f.mostly(words, m.features.map((x) => f.features[x] ?? x).join(", "));
    }
    if (m.set_aside) {
      const name = f.modelNames[m.set_aside.model] ?? f.models[m.set_aside.model] ?? "";
      const aside = f.setAside(
        name,
        formatPercent(m.set_aside.gain),
        biasText(m.set_aside.bias, r.kind),
      );
      return `${words}. ${aside}`;
    }
    return words;
  };
}

function RestsOnTable({ rows }: { rows: ForecastReliabilityOut[] }) {
  const { t } = useI18n();
  const f = t.forecast;
  const method = useMethodText();
  const biasText = useBiasText();
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-muted">{t.common.showData}</summary>
      <div className="mt-2">
        <WordTable
          label={f.restsTitle}
          head={[
            f.colCategory,
            f.colMethod,
            f.colKnown,
            f.colMase,
            f.colWape,
            f.colVsBaseline,
            f.colBias,
            f.colCoverage,
          ]}
          rows={rows.map((r) => [
            r.name,
            method(r),
            formatEurWhole(r.known),
            r.mase === null ? "—" : formatRatio(r.mase),
            r.wape === null ? "—" : formatPercent(r.wape),
            r.versus === null
              ? "—"
              : Number(r.versus) > 0
                ? f.better(formatPercent(r.versus))
                : f.same,
            biasText(r.bias, r.kind),
            r.coverage === null ? "—" : formatPercent(r.coverage),
          ])}
          text={2}
          worded={[5, 6]}
        />
      </div>
    </details>
  );
}

function ScoresTable({ scores }: { scores: ForecastScoreOut[] }) {
  const { t } = useI18n();
  const f = t.forecast;
  const biasText = useBiasText();
  const kind = { income: "income", spent: "expense", saved: "savings" } as const;
  const bias = (s: ForecastScoreOut) => {
    if (s.name !== "rest") return biasText(s.bias_share, kind[s.name]);
    if (s.bias_per_month === null) return "—";
    const n = Number(s.bias_per_month);
    if (Math.abs(n) < 1) return f.biasNone;
    const amount = formatEurWhole(Math.abs(n));
    return n < 0 ? f.biasRestAbove(amount) : f.biasRestBelow(amount);
  };
  return (
    <WordTable
      label={f.backtestTitle}
      head={[f.colTotal, f.colMase, f.colWape, f.colRmsse, f.colBias]}
      rows={scores.map((s) => [
        f[s.name],
        s.mase === null ? "—" : formatRatio(s.mase),
        s.wape === null ? "—" : formatPercent(s.wape),
        s.rmsse === null ? "—" : formatRatio(s.rmsse),
        bias(s),
      ])}
      worded={[4]}
    />
  );
}
