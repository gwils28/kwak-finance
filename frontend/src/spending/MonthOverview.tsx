import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type ReactNode, useState } from "react";
import {
  createLine,
  type FixedOccurrenceOut,
  type SpendingMonthOut,
  type SpendingProgressLineOut,
  type SpendingSavingsLineOut,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button, ErrorAlert } from "../components/ui";
import { SpendingPace } from "../dashboard/charts";
import { useI18n } from "../i18n";
import { formatDate } from "../lib/dates";
import {
  formatEur,
  formatEurSigned,
  formatEurWhole,
  formatPercent,
  formatPercentSigned,
} from "../lib/money";
import { monthLabel, thisMonth } from "../lib/months";
import { incomeIds, isIncomeLine, negate, typedOf } from "./draft";
import { BAR, ICON, Threshold } from "./progress";
import {
  linesQuery,
  occurrencesQuery,
  refreshSpending,
  spendingCategoriesQuery,
  summaryQuery,
} from "./queries";

const BOX = "flex flex-col gap-3 rounded-lg border border-border bg-surface p-4";

/**
 * The overview's spending (F-DSH-1, 4, F-BUD-2, F-FIX-4): the month's figures, the month so far
 * (the spending targets, then the savings objectives), the fixed expenses still to confirm and the last lines entered.
 */
export function MonthOverview({ month, isOwner }: { month: string; isOwner: boolean }) {
  const { t } = useI18n();
  const summary = useQuery(summaryQuery(month));
  const lines = useQuery(linesQuery(month));

  if (summary.isError) return <ErrorAlert message={t.dashboard.loadFailed} />;
  if (!summary.data || !lines.data) return <p className="text-sm text-muted">{t.common.loading}</p>;
  if (lines.data.last_entry === null) {
    return (
      <section className="rounded-lg border border-border bg-surface p-6">
        <p>{t.dashboard.empty}</p>
        <Link to="/spending" className="mt-3 inline-block text-accent hover:underline">
          {t.dashboard.goToLines}
        </Link>
      </section>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <Figures summary={summary.data} />
      <MonthSoFar summary={summary.data} isOwner={isOwner} />
      <SavingsSoFar summary={summary.data} />
      <ToConfirm month={month} projectedRest={summary.data.projected_rest} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Top summary={summary.data} />
        <SpendingPace
          month={month}
          cumulative={summary.data.cumulative}
          target={summary.data.target_total}
        />
      </div>
      <LastLines month={month} />
    </div>
  );
}

function Tile({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <section
      aria-label={label}
      className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="text-sm text-muted">{label}</h2>
      <p className="text-2xl font-semibold">{value}</p>
      {children && <div className="text-xs">{children}</div>}
    </section>
  );
}

/** Spending going up is bad: an arrow and words carry it, the colour only reinforces. */
function SpendingChange({ ratio, against }: { ratio: string | null; against: string }) {
  const { t } = useI18n();
  if (ratio === null) return null;
  const up = Number(ratio) > 0;
  return (
    <p className={up ? "text-negative" : "text-positive"}>
      <span aria-hidden="true">{up ? "▲" : "▼"} </span>
      {t.dashboard.versus(formatPercentSigned(ratio), against)}
    </p>
  );
}

function Figures({ summary }: { summary: SpendingMonthOut }) {
  const { t } = useI18n();
  const o = t.overview;
  const f = summary.figures;
  const vsPrevious = summary.changes.vs_previous.spent;
  const vsAverage = summary.changes.vs_average?.spent ?? null;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Tile label={t.dashboard.income} value={formatEurWhole(f.income)} />
      <Tile label={t.dashboard.spent} value={formatEurWhole(f.spent)}>
        {vsPrevious === null && vsAverage === null ? (
          <p className="text-muted">{t.dashboard.nothingToCompare}</p>
        ) : (
          <>
            <SpendingChange ratio={vsPrevious} against={t.dashboard.lastMonth} />
            <SpendingChange ratio={vsAverage} against={t.dashboard.yearAverage} />
          </>
        )}
      </Tile>
      <Tile label={t.spending.saved} value={formatEurWhole(f.saved)}>
        <p className="text-muted">{o.savedHelp}</p>
      </Tile>
      <Tile label={o.rest} value={formatEurSigned(f.rest)}>
        <p className="text-muted">{o.restHelp}</p>
        {summary.to_confirm > 0 && (
          <p>{o.projectedRest(formatEurSigned(summary.projected_rest))}</p>
        )}
      </Tile>
      <Tile
        label={t.dashboard.savingsRate}
        value={f.savings_rate === null ? "—" : formatPercent(f.savings_rate)}
      >
        <p className="text-muted">
          {f.savings_rate === null ? t.dashboard.noIncome : o.savingsRateHelp}
        </p>
      </Tile>
    </div>
  );
}

/** The month so far (F-BUD-2): each category with a target, highest share used first. */
function MonthSoFar({ summary, isOwner }: { summary: SpendingMonthOut; isOwner: boolean }) {
  const { t } = useI18n();
  const lines = summary.progress.lines;
  const hasPace = lines.some((line) => line.pace !== null);
  return (
    <section aria-label={t.dashboard.targets.titleOf(monthLabel(summary.month))} className={BOX}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{t.dashboard.targets.title}</h2>
        <Threshold warnAt={summary.progress.warn_at} isOwner={isOwner} />
      </div>
      {lines.length === 0 ? (
        <p className="text-sm text-muted">
          {t.overview.noTargets}{" "}
          <Link to="/budget" className="text-accent hover:underline">
            {t.overview.setTargets}
          </Link>
        </p>
      ) : (
        <>
          <ul className="flex flex-col gap-3">
            {lines.map((line) => (
              <ProgressLine key={line.category_id} line={line} month={summary.month} />
            ))}
          </ul>
          {hasPace && <p className="text-xs text-muted">{t.dashboard.targets.paceLegend}</p>}
        </>
      )}
    </section>
  );
}

function ProgressLine({ line, month }: { line: SpendingProgressLineOut; month: string }) {
  const { t } = useI18n();
  const tg = t.dashboard.targets;
  const over = line.remaining.startsWith("-");
  const filled =
    line.share === null ? (over ? 1 : 0) : Math.min(Math.max(Number(line.share), 0), 1);
  return (
    <li className="flex flex-col gap-1 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <Link
          to="/spending"
          search={{ month, category: line.category_id }}
          aria-label={t.overview.openLines(line.name)}
          className="font-medium hover:text-accent hover:underline"
        >
          {line.name}
        </Link>
        <span className="tabular text-muted">
          {tg.spentOf(formatEurWhole(line.spent), formatEurWhole(line.target))}
          {" · "}
          {over
            ? tg.overBy(formatEurWhole(line.remaining.slice(1)))
            : tg.left(formatEurWhole(line.remaining))}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-border">
        <div
          className={`h-2 rounded-full ${BAR[line.status]}`}
          style={{ width: `${filled * 100}%` }}
        />
        {line.pace !== null && (
          <div
            aria-hidden="true"
            className="absolute -top-1 h-4 w-0.5 rounded bg-fg"
            style={{ left: `calc(${Number(line.pace) * 100}% - 1px)` }}
          />
        )}
      </div>
      <div className="flex flex-wrap justify-between gap-x-3 text-xs">
        <span className={line.status === "on_track" ? "text-muted" : "font-semibold"}>
          <span aria-hidden="true">{ICON[line.status]} </span>
          {tg.status[line.status]}
          {line.share !== null && ` · ${tg.used(formatPercent(line.share))}`}
        </span>
        <span className="text-muted">
          {/* No pace for a one-off category, nor for a month other than this one. */}
          {line.pace !== null
            ? tg.pace(formatPercent(line.pace))
            : month === thisMonth()
              ? tg.oneOff
              : null}
        </span>
      </div>
    </li>
  );
}

/** The month's savings objectives (F-BUD-2, F-BUD-9): reached or in progress, least advanced first. */
function SavingsSoFar({ summary }: { summary: SpendingMonthOut }) {
  const { t } = useI18n();
  const s = t.overview.savingsTargets;
  const lines = summary.progress.savings;
  return (
    <section aria-label={s.titleOf(monthLabel(summary.month))} className={BOX}>
      <h2 className="font-semibold">{s.title}</h2>
      {lines.length === 0 ? (
        <p className="text-sm text-muted">
          {s.none}{" "}
          <Link to="/budget" className="text-accent hover:underline">
            {t.overview.setTargets}
          </Link>
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {lines.map((line) => (
            <SavingsLine key={line.category_id} line={line} month={summary.month} />
          ))}
        </ul>
      )}
    </section>
  );
}

function SavingsLine({ line, month }: { line: SpendingSavingsLineOut; month: string }) {
  const { t } = useI18n();
  const s = t.overview.savingsTargets;
  const reached = line.status === "reached";
  const beyond = line.remaining.startsWith("-");
  const filled =
    line.share === null ? (reached ? 1 : 0) : Math.min(Math.max(Number(line.share), 0), 1);
  return (
    <li className="flex flex-col gap-1 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <Link
          to="/spending"
          search={{ month, category: line.category_id }}
          aria-label={t.overview.openLines(line.name)}
          className="font-medium hover:text-accent hover:underline"
        >
          {line.name}
        </Link>
        <span className="tabular text-muted">
          {s.savedOf(formatEurWhole(line.saved), formatEurWhole(line.objective))}
          {Number(line.remaining) !== 0 &&
            ` · ${
              beyond
                ? s.beyond(formatEurWhole(line.remaining.slice(1)))
                : s.toGo(formatEurWhole(line.remaining))
            }`}
        </span>
      </div>
      <div className="h-2 rounded-full bg-border">
        <div
          className={`h-2 rounded-full ${reached ? "bg-flow-saved" : "bg-flow-saved-behind"}`}
          style={{ width: `${filled * 100}%` }}
        />
      </div>
      <span className={`text-xs ${reached ? "font-semibold" : "text-muted"}`}>
        <span aria-hidden="true">{reached ? "✓" : "…"} </span>
        {s.status[line.status]}
        {line.share !== null && ` · ${s.share(formatPercent(line.share))}`}
      </span>
    </li>
  );
}

/** F-FIX-4: the month's fixed expenses still to confirm, and the rest once they are paid. */
function ToConfirm({ month, projectedRest }: { month: string; projectedRest: string }) {
  const { t } = useI18n();
  const c = t.overview.toConfirm;
  const queryClient = useQueryClient();
  const occurrences = useQuery(occurrencesQuery(month));
  const categories = useQuery(spendingCategoriesQuery);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = (occurrences.data ?? []).filter((o) => o.status === "to_confirm");
  if (!occurrences.data || occurrences.data.length === 0) return null;

  const confirm = async (o: FixedOccurrenceOut) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await createLine({
        body: {
          day: o.due,
          label: o.label,
          amount: o.amount,
          category_id: o.category_id,
          fixed_expense_id: o.fixed_expense_id,
        },
        throwOnError: true,
      });
      await refreshSpending(queryClient);
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-label={c.title} className={BOX}>
      <h2 className="font-semibold">{c.title}</h2>
      {pending.length === 0 ? (
        <p className="text-sm text-muted">{c.none}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border text-sm">
          {pending.map((o) => (
            <li
              key={`${o.fixed_expense_id}-${o.due}`}
              className="flex flex-wrap items-center gap-3 py-2"
            >
              <span className="w-28 text-muted">{formatDate(o.due)}</span>
              <span className="flex-1">{o.label}</span>
              <span className="text-muted">
                {categories.data?.find((cat) => cat.id === o.category_id)?.name}
              </span>
              <span className="tabular w-24 text-right">{formatEur(negate(o.amount))}</span>
              <Button
                variant="ghost"
                className="py-1"
                disabled={busy}
                aria-label={c.confirm(o.label)}
                onClick={() => void confirm(o)}
              >
                {t.spending.fixed.confirm}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <ErrorAlert message={error} />
      <p className="text-sm font-medium">{c.projected(formatEurSigned(projectedRest))}</p>
    </section>
  );
}

function Top({ summary }: { summary: SpendingMonthOut }) {
  const { t } = useI18n();
  const categories = useQuery(spendingCategoriesQuery);
  const nameOf = (id: string) => categories.data?.find((c) => c.id === id)?.name ?? "";
  return (
    <section aria-label={t.dashboard.topCategories} className={BOX}>
      <h2 className="font-semibold">{t.dashboard.topCategories}</h2>
      {summary.top.length === 0 ? (
        <p className="text-sm text-muted">{t.dashboard.noCategorised}</p>
      ) : (
        <ol className="flex flex-col divide-y divide-border text-sm">
          {summary.top.map((c) => (
            <li key={c.category_id} className="flex items-baseline gap-3 py-2">
              <Link
                to="/spending"
                search={{ month: summary.month, category: c.category_id }}
                className="flex-1 truncate hover:text-accent hover:underline"
              >
                {nameOf(c.category_id)}
              </Link>
              <span className="tabular font-semibold">{formatEurWhole(c.spent)}</span>
              {c.share !== null && (
                <span className="tabular w-12 text-right text-muted">
                  {formatPercent(c.share)}
                  <span className="sr-only"> {t.dashboard.ofSpending}</span>
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function LastLines({ month }: { month: string }) {
  const { t } = useI18n();
  const l = t.overview.lastLines;
  const lines = useQuery(linesQuery(month));
  const categories = useQuery(spendingCategoriesQuery);
  const latest = [...(lines.data?.lines ?? [])]
    .sort((a, b) => b.entered_at.localeCompare(a.entered_at))
    .slice(0, 5);
  const income = incomeIds(categories.data ?? []);
  const nameOf = (id: string | null) =>
    id === null ? t.spending.split.title : (categories.data?.find((c) => c.id === id)?.name ?? "");
  return (
    <section aria-label={l.title} className={BOX}>
      <h2 className="font-semibold">{l.title}</h2>
      {latest.length === 0 ? (
        <p className="text-sm text-muted">{l.none}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border text-sm">
          {latest.map((line) => (
            <li key={line.id} className="flex flex-wrap items-baseline gap-3 py-2">
              <span className="w-28 text-muted">{formatDate(line.day)}</span>
              <span className="flex-1 truncate">{line.label}</span>
              <span className="text-muted">{nameOf(line.category_id)}</span>
              <span className="tabular w-24 text-right">
                {formatEur(typedOf(line.amount, isIncomeLine(line, income)))}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link
        to="/spending"
        search={{ month }}
        className="self-start text-sm font-medium text-accent hover:underline"
      >
        {l.open}
      </Link>
    </section>
  );
}
