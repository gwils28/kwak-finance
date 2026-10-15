/**
 * What both wealth pages share: the scope and the months shown, the matrix they read, the
 * controls that choose them, and the summary tiles.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { type ReactNode, useId, useState } from "react";
import { type Scope, type WealthMatrixOut, wealthMatrix } from "../api/generated";
import { ScopeSelect } from "../components/ScopeSelect";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEurSigned, formatEurWhole, formatPercent, formatPercentSigned } from "../lib/money";
import { isMonth, monthLabel, thisMonth } from "../lib/months";

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
const labelClass = "flex flex-col gap-1 text-sm font-medium";
const MAX_MONTHS = 120;

type Period = { start: string; end: string };

const monthIndex = (month: string) => {
  const [year, m] = month.split("-").map(Number) as [number, number];
  return year * 12 + m;
};

export type WealthView = ReturnType<typeof useWealthView>;

/** The scope and the months asked for (null: the last 12, from the wealth start), and the matrix. */
export function useWealthView() {
  const [scope, setScope] = useState<Scope>("household");
  const [period, setPeriod] = useState<Period | null>(null);
  // The months being typed, shown even while incomplete or wrong.
  const [draft, setDraft] = useState<Period | null>(null);
  const matrix = useQuery({
    queryKey: ["wealth", "matrix", scope, period],
    queryFn: async () =>
      (await wealthMatrix({ query: { scope, ...period }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });
  return { scope, setScope, period, setPeriod, draft, setDraft, matrix };
}

/** The scope and the From / To months. */
export function ViewControls({ view }: { view: WealthView }) {
  const { scope, setScope, period, setPeriod, draft, setDraft, matrix } = view;
  const data = matrix.data;
  return (
    <>
      <ScopeSelect
        value={scope}
        onChange={setScope}
        labelClassName={labelClass}
        fieldClassName={fieldClass}
      />
      {data && (
        <PeriodPicker
          shown={{ start: data.months[0] ?? "", end: data.months.at(-1) ?? "" }}
          draft={draft}
          onChange={(next) => {
            setDraft(next);
            if (periodProblem(next) === null) setPeriod(next);
          }}
          onReset={
            draft || period
              ? () => {
                  setDraft(null);
                  setPeriod(null);
                }
              : null
          }
        />
      )}
    </>
  );
}

type PeriodProblem = "endsBeforeStart" | "tooLong" | "incomplete";

function periodProblem({ start, end }: Period): PeriodProblem | null {
  if (!isMonth(start) || !isMonth(end) || end > thisMonth()) return "incomplete";
  if (end < start) return "endsBeforeStart";
  return monthIndex(end) - monthIndex(start) + 1 > MAX_MONTHS ? "tooLong" : null;
}

function PeriodPicker({
  shown,
  draft,
  onChange,
  onReset,
}: {
  shown: Period;
  draft: Period | null;
  onChange: (period: Period) => void;
  onReset: (() => void) | null;
}) {
  const { t } = useI18n();
  const ids = { from: useId(), to: useId() };
  const value = draft ?? shown;
  const problem = draft ? periodProblem(draft) : null;
  return (
    <>
      <label htmlFor={ids.from} className={labelClass}>
        {t.wealth.from}
        <input
          id={ids.from}
          type="month"
          className={fieldClass}
          value={value.start}
          max={thisMonth()}
          onChange={(e) => onChange({ ...value, start: e.target.value })}
        />
      </label>
      <label htmlFor={ids.to} className={labelClass}>
        {t.wealth.to}
        <input
          id={ids.to}
          type="month"
          className={fieldClass}
          value={value.end}
          max={thisMonth()}
          onChange={(e) => onChange({ ...value, end: e.target.value })}
        />
      </label>
      {onReset && (
        <Button variant="ghost" onClick={onReset}>
          {t.wealth.last12}
        </Button>
      )}
      {(problem === "endsBeforeStart" || problem === "tooLong") && (
        <div className="basis-full">
          <ErrorAlert message={t.wealth[problem]} />
        </div>
      )}
    </>
  );
}

function Tile({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <section
      aria-label={label}
      className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="text-sm text-muted">{label}</h2>
      <p className="tabular text-2xl font-semibold">{value}</p>
      {children && <div className="text-xs text-muted">{children}</div>}
    </section>
  );
}

export function Summary({ matrix }: { matrix: WealthMatrixOut }) {
  const { t } = useI18n();
  const last = matrix.months.length - 1;
  if (last < 0) return null;
  const change = matrix.change[last];
  const gross = matrix.gross[last] as string;
  // Over the months shown: against the first one's net worth, when it held something.
  const first = Number(matrix.net[0]);
  const moved = Number(matrix.net[last]) - first;
  const since =
    last > 0 && first !== 0 ? changeText(String(moved), String(moved / Math.abs(first))) : null;
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <Tile label={t.wealth.netWorth} value={formatEurWhole(matrix.net[last] as string)}>
        <p>
          {change
            ? t.wealth.versusLastMonth(changeText(change, matrix.change_ratio[last] ?? null))
            : t.wealth.nothingBefore}
        </p>
        {since && <p>{t.wealth.sinceStart(since, monthLabel(matrix.months[0] as string))}</p>}
      </Tile>
      <Tile label={t.wealth.gross} value={formatEurWhole(gross)} />
      <Tile label={t.wealth.debts} value={formatEurWhole(matrix.debts[last] as string)}>
        {Number(gross) > 0 &&
          t.wealth.debtRatio(formatPercent(Number(matrix.debts[last]) / Number(gross)))}
      </Tile>
    </div>
  );
}

/** "+€650 · +8%": the change in euros, and in % of the month before when there is one. */
export function changeText(change: string, ratio: string | null): string {
  return ratio === null
    ? formatEurSigned(change)
    : `${formatEurSigned(change)} · ${formatPercentSigned(ratio)}`;
}
