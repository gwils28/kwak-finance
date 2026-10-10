import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useId, useState } from "react";
import {
  type BudgetStatus,
  budgetMatrix,
  type CellOut,
  listPlans,
  type PlanOut,
  type RowOut,
  type Scope,
  setPlanTarget,
} from "../api/generated";
import { apiErrorMessage, detailSentence } from "../auth/errors";
import { ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import {
  amountInputShort,
  formatEurSigned,
  formatEurWhole,
  formatPercent,
  formatPercentSigned,
  parseEurInput,
} from "../lib/money";
import { monthBounds, monthLabel, shiftMonth, thisMonth } from "../lib/months";
import { defaultPlan, type PlanTarget, planTargets } from "../lib/plans";
import { PLANS_KEY, PlanPanel, usePeriodLabel } from "./PlanPanel";

const STATUS_CLASS: Record<BudgetStatus, string> = {
  under: "bg-budget-under-bg text-budget-under-fg",
  on: "bg-budget-on-bg text-budget-on-fg",
  over: "bg-budget-over-bg text-budget-over-fg",
  none: "",
};

export { thisMonth };

/** "60.00" -> "60", "12.50" -> "12,50" (fr): how a target reads in its input. */
function targetText(target: PlanTarget | undefined): string {
  if (!target || target.fromChildren) return "";
  return amountInputShort(target.amount);
}

const fieldClass = "rounded-md border border-border bg-surface px-3 py-2";
// The category and target columns stay visible while the months scroll sideways.
const STICKY_NAME = "sticky left-0 z-10 w-52 min-w-52 bg-surface";
const STICKY_TARGET = "sticky left-52 z-10 w-40 min-w-40 bg-surface border-r border-border";

export function BudgetPage() {
  const { t } = useI18n();
  const ids = { period: useId(), scope: useId(), band: useId() };
  const [period, setPeriod] = useState(12);
  const [scope, setScope] = useState<Scope>("household");
  const [band, setBand] = useState("0.05");
  const [error, setError] = useState<string | null>(null);
  const [showEmpty, setShowEmpty] = useState(false);
  const [planId, setPlanId] = useState<string | null>(null);
  const periodLabel = usePeriodLabel();
  const end = thisMonth();
  const start = shiftMonth(end, -(period - 1));

  const matrix = useQuery({
    queryKey: ["budget", { start, end, scope, band }],
    queryFn: async () =>
      (await budgetMatrix({ query: { start, end, scope, band }, throwOnError: true })).data,
    placeholderData: keepPreviousData,
  });

  const plans = useQuery({
    queryKey: PLANS_KEY,
    queryFn: async () => (await listPlans({ throwOnError: true })).data,
  });
  const plan = plans.data?.find((p) => p.id === planId) ?? defaultPlan(plans.data ?? [], end);
  const targets = plan && matrix.data ? planTargets(plan, matrix.data.rows) : null;

  const bandPercent = formatPercent(band);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{t.budget.title}</h1>
          <p className="text-sm text-muted">{t.budget.intro}</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <label htmlFor={ids.period} className="flex flex-col gap-1 text-sm font-medium">
            {t.budget.period}
            <select
              id={ids.period}
              className={fieldClass}
              value={period}
              onChange={(e) => setPeriod(Number(e.target.value))}
            >
              {[3, 6, 12].map((n) => (
                <option key={n} value={n}>
                  {t.budget.lastMonths(n)}
                </option>
              ))}
            </select>
          </label>
          <label htmlFor={ids.scope} className="flex flex-col gap-1 text-sm font-medium">
            {t.dashboard.scope}
            <select
              id={ids.scope}
              className={fieldClass}
              value={scope}
              onChange={(e) => setScope(e.target.value as Scope)}
            >
              <option value="household">{t.dashboard.household}</option>
              <option value="mine">{t.dashboard.mine}</option>
            </select>
          </label>
          <label htmlFor={ids.band} className="flex flex-col gap-1 text-sm font-medium">
            {t.budget.margin}
            <select
              id={ids.band}
              className={fieldClass}
              value={band}
              onChange={(e) => setBand(e.target.value)}
            >
              {["0.05", "0.10", "0.15"].map((value) => (
                <option key={value} value={value}>
                  ± {formatPercent(value)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {plans.isError && <ErrorAlert message={t.budget.loadFailed} />}
      {plans.data && (
        <PlanPanel plans={plans.data} selected={plan} onSelect={setPlanId} onError={setError} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Legend band={bandPercent} />
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={showEmpty}
            onChange={(e) => setShowEmpty(e.target.checked)}
          />
          {t.budget.showEmpty}
        </label>
      </div>
      <ErrorAlert message={error} />
      {matrix.isError && <ErrorAlert message={t.budget.loadFailed} />}
      {matrix.isPending && <p className="text-sm text-muted">{t.common.loading}</p>}
      {matrix.data && (
        <div className="overflow-x-auto rounded-lg border border-border bg-surface">
          <table aria-label={t.budget.table} className="w-full text-sm">
            <thead className="text-left text-muted">
              <tr>
                <th className={`${STICKY_NAME} px-3 py-2 font-medium`}>{t.budget.category}</th>
                <th className={`${STICKY_TARGET} px-3 py-2 font-medium`}>
                  {plan
                    ? t.budget.monthlyTargetOf(periodLabel(plan.period))
                    : t.budget.monthlyTarget}
                </th>
                {matrix.data.months.map((m) => (
                  <th key={m} className="whitespace-nowrap px-3 py-2 text-right font-medium">
                    {monthLabel(m)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visibleRows(matrix.data.rows, showEmpty).map((row) => (
                <MatrixRow
                  key={row.category_id}
                  row={row}
                  plan={plan}
                  target={row.category_id ? targets?.byCategory.get(row.category_id) : undefined}
                  onError={setError}
                  categoryParam={row.category_id ?? "none"}
                />
              ))}
              <MatrixRow row={matrix.data.uncategorised} onError={setError} categoryParam="none" />
              <MatrixRow
                row={matrix.data.total}
                target={targets?.total ? { amount: targets.total, fromChildren: true } : undefined}
                onError={setError}
                isTotal
              />
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function isEmpty(row: RowOut): boolean {
  return row.target === null && row.cells.every((c) => Number(c.spent) === 0);
}

/** Without `showEmpty`, drop rows with nothing to say; a parent stays while a child shows. */
function visibleRows(rows: RowOut[], showEmpty: boolean): RowOut[] {
  if (showEmpty) return rows;
  const kept = new Set(rows.filter((r) => !isEmpty(r)).map((r) => r.category_id));
  for (const row of rows) if (row.parent_id && kept.has(row.category_id)) kept.add(row.parent_id);
  return rows.filter((r) => kept.has(r.category_id));
}

function Legend({ band }: { band: string }) {
  const { t } = useI18n();
  const swatch = "inline-block h-3 w-3 rounded-sm align-middle";
  return (
    <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
      <span>
        <span className={`${swatch} bg-budget-under-bg`} /> {t.budget.legendUnder(band)}
      </span>
      <span>
        <span className={`${swatch} bg-budget-on-bg`} /> {t.budget.legendOn(band)}
      </span>
      <span>
        <span className={`${swatch} bg-budget-over-bg`} /> {t.budget.legendOver(band)}
      </span>
      <span>{t.budget.legendNone}</span>
    </p>
  );
}

function MatrixRow({
  row,
  plan,
  target,
  onError,
  isTotal = false,
  categoryParam,
}: {
  row: RowOut;
  /** The plan whose targets the row edits; none for the "to categorise" and total rows. */
  plan?: PlanOut;
  target?: PlanTarget;
  onError: (message: string | null) => void;
  isTotal?: boolean;
  categoryParam?: string;
}) {
  const { t } = useI18n();
  const weight = row.level === 0 ? "font-semibold" : "";
  const rowClass = isTotal ? "border-t-2 border-border font-bold" : "";
  return (
    <tr className={rowClass}>
      <th
        scope="row"
        className={`${STICKY_NAME} whitespace-nowrap px-3 py-2 text-left ${weight} ${
          row.level === 1 ? "pl-8 font-normal" : ""
        }`}
      >
        {row.name}
      </th>
      <td className={`${STICKY_TARGET} px-3 py-2`}>
        {plan?.editable && row.category_id ? (
          <TargetInput
            key={`${plan.id}:${target?.amount}`}
            row={row}
            plan={plan}
            target={target}
            categoryId={row.category_id}
            onError={onError}
          />
        ) : (
          <span
            className="tabular text-muted"
            title={plan && !plan.editable ? t.budget.plan.lockedTarget : undefined}
          >
            {target ? formatEurWhole(target.amount) : ""}
          </span>
        )}
      </td>
      {row.cells.map((cell) => (
        <MatrixCell key={cell.month} row={row} cell={cell} categoryParam={categoryParam} />
      ))}
    </tr>
  );
}

function MatrixCell({
  row,
  cell,
  categoryParam,
}: {
  row: RowOut;
  cell: CellOut;
  categoryParam: string | undefined;
}) {
  const spent = formatEurWhole(cell.spent);
  const gap =
    cell.gap !== null && cell.gap_ratio !== null
      ? `${formatEurSigned(cell.gap)} · ${formatPercentSigned(cell.gap_ratio)}`
      : null;
  const content = (
    <>
      <span className="tabular block">{spent}</span>
      {gap && <span className="tabular block text-xs opacity-80">{gap}</span>}
    </>
  );
  return (
    <td
      data-status={cell.status}
      className={`whitespace-nowrap px-3 py-2 text-right ${STATUS_CLASS[cell.status]}`}
    >
      {categoryParam ? (
        <Link
          to="/transactions"
          search={{ category: categoryParam, ...monthBounds(cell.month) }}
          aria-label={`${row.name}, ${monthLabel(cell.month)}: ${spent}`}
          className="block hover:underline"
        >
          {content}
        </Link>
      ) : (
        content
      )}
    </td>
  );
}

function TargetInput({
  row,
  plan,
  target,
  categoryId,
  onError,
}: {
  row: RowOut;
  plan: PlanOut;
  target: PlanTarget | undefined;
  categoryId: string;
  onError: (message: string | null) => void;
}) {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [text, setText] = useState(targetText(target));
  const save = useMutation({
    mutationFn: async (amount: string | null) => {
      const { data, error, response } = await setPlanTarget({
        path: { plan_id: plan.id, category_id: categoryId },
        body: { amount },
      });
      if (!data) throw new Error(detailSentence(error) ?? apiErrorMessage(t, response));
      return data;
    },
    onSuccess: () => {
      onError(null);
      return queryClient.invalidateQueries({ queryKey: ["budget"] });
    },
    onError: (exc) => onError(`${row.name}: ${exc.message}`),
  });

  const commit = () => {
    if (text.trim() === targetText(target)) return;
    if (text.trim() === "") {
      save.mutate(null);
      return;
    }
    const amount = parseEurInput(text);
    if (amount === null || amount.startsWith("-")) {
      onError(`${row.name}: ${t.budget.invalidTarget}`);
      return;
    }
    save.mutate(amount);
  };

  return (
    <input
      aria-label={t.budget.targetFor(row.name)}
      inputMode="decimal"
      placeholder={target?.fromChildren ? t.budget.sum(formatEurWhole(target.amount)) : "—"}
      title={target?.fromChildren ? t.budget.sumHelp : undefined}
      className="tabular w-32 rounded-md border border-border bg-surface px-2 py-1 text-right"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
    />
  );
}
