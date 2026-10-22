import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, Link } from "@tanstack/react-router";
import { type FormEvent, useId, useState } from "react";
import {
  type BudgetStatus,
  removeTarget,
  type SpendingCategoryOut,
  type SpendingCellOut,
  type SpendingMatrixRowOut,
  setTarget,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { InView } from "../components/InView";
import { SCROLL_FRAME, STICKY_CORNER, STICKY_LEFT, STICKY_TOP } from "../components/stickyTable";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import {
  amountInputShort,
  formatEurSigned,
  formatEurWhole,
  formatPercentSigned,
  isZero,
  parseEurInput,
} from "../lib/money";
import { monthLabel, shiftMonth, thisMonth } from "../lib/months";
import { matrixQuery, refreshSpending, spendingCategoriesQuery, targetsQuery } from "./queries";
import { YearView } from "./YearView";

export type BudgetSearch = { view?: "year"; months?: number; year?: number };

const PERIODS = [3, 6, 12, 24];

/** Search params of /budget, validated: anything malformed is dropped. */
export function parseBudgetSearch(search: Record<string, unknown>): BudgetSearch {
  const months = Number(search.months);
  const year = Number(search.year);
  return {
    view: search.view === "year" ? "year" : undefined,
    months: PERIODS.includes(months) ? months : undefined,
    year: Number.isInteger(year) && year >= 1900 && year <= 2200 ? year : undefined,
  };
}

const route = getRouteApi("/app/budget");
// The target column stays in view next to the categories' (10rem wide).
const TARGET_COL = "sticky left-40 z-10 bg-surface";
const TARGET_HEAD =
  "sticky top-0 left-40 z-30 bg-surface shadow-[inset_0_-1px_0_var(--color-border)]";
const field = "rounded-md border border-border bg-surface px-3 py-2";

/** A cell's colour; the status is also said in words. */
export const LOOK: Record<BudgetStatus, string> = {
  under: "bg-budget-under-bg text-budget-under-fg",
  ahead: "bg-budget-under-bg text-budget-under-fg",
  on: "bg-budget-on-bg text-budget-on-fg",
  over: "bg-budget-over-bg text-budget-over-fg",
  behind: "bg-budget-over-bg text-budget-over-fg",
  none: "",
};

/** The budget (F-BUD-1, 6, 9, 10): the matrix by month, or the year. */
export function BudgetPage() {
  const { t } = useI18n();
  const b = t.spendingBudget;
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const ids = { period: useId(), year: useId() };
  const current = thisMonth();
  const thisYear = Number(current.slice(0, 4));
  const tab = (active: boolean) =>
    `rounded-full px-3 py-1 text-sm font-medium ${active ? "bg-accent text-bg" : "text-muted hover:text-fg"}`;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-black tracking-tight">{b.title}</h1>
          <p className="text-sm text-muted">{b.intro}</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <nav aria-label={b.views} className="flex gap-1 rounded-full border border-border p-0.5">
            <Link
              to="/budget"
              search={{ months: search.months }}
              aria-current={search.view ? undefined : "page"}
              className={tab(!search.view)}
            >
              {b.byMonth}
            </Link>
            <Link
              to="/budget"
              search={{ view: "year", year: search.year }}
              aria-current={search.view ? "page" : undefined}
              className={tab(Boolean(search.view))}
            >
              {b.year}
            </Link>
          </nav>
          {search.view === "year" ? (
            <label htmlFor={ids.year} className="flex flex-col gap-1 text-sm font-medium">
              {b.yearChoice}
              <select
                id={ids.year}
                className={field}
                value={search.year ?? thisYear}
                onChange={(e) =>
                  void navigate({ search: (prev) => ({ ...prev, year: Number(e.target.value) }) })
                }
              >
                {[
                  ...new Set([
                    ...Array.from({ length: 6 }, (_, i) => thisYear - i),
                    search.year ?? thisYear,
                  ]),
                ]
                  .sort((a, b) => b - a)
                  .map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
              </select>
            </label>
          ) : (
            <label htmlFor={ids.period} className="flex flex-col gap-1 text-sm font-medium">
              {b.period}
              <select
                id={ids.period}
                className={field}
                value={search.months ?? 12}
                onChange={(e) =>
                  void navigate({
                    search: (prev) => ({ ...prev, months: Number(e.target.value) }),
                  })
                }
              >
                {PERIODS.map((n) => (
                  <option key={n} value={n}>
                    {b.lastMonths(n)}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>
      {search.view === "year" ? (
        <YearView year={search.year ?? thisYear} />
      ) : (
        <Matrix first={shiftMonth(current, -((search.months ?? 12) - 1))} last={current} />
      )}
    </div>
  );
}

function Matrix({ first, last }: { first: string; last: string }) {
  const { t } = useI18n();
  const b = t.spendingBudget;
  const matrix = useQuery(matrixQuery(first, last));
  const categories = useQuery(spendingCategoriesQuery);
  const [editing, setEditing] = useState<{
    category: SpendingCategoryOut;
    target: string | null;
  } | null>(null);
  const [notice, setNotice] = useState("");

  if (matrix.isError) return <ErrorAlert message={t.errors.generic} />;
  if (!matrix.data || !categories.data) return <p>{t.common.loading}</p>;
  const data = matrix.data;
  const byId = new Map(categories.data.map((c) => [c.id, c]));
  const width = data.months.length + 2;

  const row = (r: SpendingMatrixRowOut, total = false) => {
    const category = r.category_id ? byId.get(r.category_id) : undefined;
    return (
      <tr
        key={r.category_id ?? r.name}
        className={`border-t border-border ${total ? "font-semibold" : ""}`}
      >
        <th
          scope="row"
          className={`${STICKY_LEFT} w-40 max-w-40 min-w-40 px-3 break-words py-2 text-left font-medium`}
        >
          {r.name}
        </th>
        <td className={`${TARGET_COL} px-2 py-2 text-right`}>
          {category ? (
            <button
              type="button"
              aria-label={b.setTarget(r.name)}
              onClick={() => {
                setNotice("");
                setEditing({ category, target: r.target });
              }}
              className="tabular rounded px-2 py-1 hover:bg-accent/10 hover:text-accent"
            >
              {r.target === null ? b.noTarget : formatEurWhole(r.target)}
            </button>
          ) : (
            <span className="tabular px-2">
              {r.target === null ? "" : formatEurWhole(r.target)}
            </span>
          )}
        </td>
        {r.cells.map((cell) => (
          <MatrixCell key={cell.month} cell={cell} name={r.name} categoryId={r.category_id} />
        ))}
      </tr>
    );
  };

  const section = (title: string) => (
    <tr>
      <th
        colSpan={width}
        scope="colgroup"
        className="px-3 pt-4 pb-1 text-left text-xs font-semibold text-muted uppercase"
      >
        {/* The cell spans the table: its title sticks, not the cell. */}
        <span className="sticky left-3">{title}</span>
      </th>
    </tr>
  );

  const figure = (label: string, key: "income" | "spent" | "saved" | "rest") => (
    <tr key={key} className="border-t border-border">
      <th scope="row" className={`${STICKY_LEFT} px-3 py-2 text-left font-medium`}>
        {label}
      </th>
      <td className={`${TARGET_COL}`} />
      {data.figures.map((f, i) => (
        <td
          key={data.months[i]}
          className={`tabular px-2 py-2 text-right ${key === "rest" && f.rest.startsWith("-") ? "text-negative" : ""}`}
        >
          {key === "rest" ? formatEurSigned(f.rest) : formatEurWhole(f[key])}
        </td>
      ))}
    </tr>
  );

  return (
    <div className="flex flex-col gap-4">
      {editing && (
        <InView key={editing.category.id}>
          <TargetEditor
            category={editing.category}
            target={editing.target}
            onDone={(message) => {
              setEditing(null);
              setNotice(message);
            }}
          />
        </InView>
      )}
      {notice && (
        <p className="rounded-md border border-accent px-3 py-2 text-sm" aria-live="polite">
          {notice}
        </p>
      )}
      <div className={SCROLL_FRAME}>
        <table className="w-full text-sm" aria-label={b.caption}>
          <thead>
            <tr>
              <th className={`${STICKY_CORNER} w-40 max-w-40 min-w-40 px-3 py-2 text-left`}>
                {b.category}
              </th>
              <th className={`${TARGET_HEAD} px-2 py-2 text-right`}>{b.target}</th>
              {data.months.map((m) => (
                <th
                  key={m}
                  scope="col"
                  className={`${STICKY_TOP} px-2 py-2 text-right whitespace-nowrap capitalize`}
                >
                  {monthLabel(m)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section(b.expenses)}
            {data.rows.map((r) => row(r))}
            {row({ ...data.total, name: b.spendingTotal }, true)}
            {section(b.savings)}
            {data.savings.map((r) => row(r))}
            {row({ ...data.savings_total, name: b.savingsTotal }, true)}
            {section(b.figures)}
            {figure(b.income, "income")}
            {figure(b.spent, "spent")}
            {figure(b.saved, "saved")}
            {figure(b.rest, "rest")}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">{b.legend}</p>
    </div>
  );
}

function MatrixCell({
  cell,
  name,
  categoryId,
}: {
  cell: SpendingCellOut;
  name: string;
  categoryId: string | null;
}) {
  const { t } = useI18n();
  const b = t.spendingBudget;
  const content = (
    <>
      <span className="block font-semibold">{formatEurWhole(cell.spent)}</span>
      {cell.gap !== null && (
        <span className="block text-xs">
          {formatEurSigned(cell.gap)}
          {cell.gap_ratio !== null && ` · ${formatPercentSigned(cell.gap_ratio)}`}
        </span>
      )}
      {cell.status !== "none" && <span className="sr-only">{b.status[cell.status]}</span>}
    </>
  );
  return (
    <td className={`tabular px-1 py-1 text-right ${LOOK[cell.status]}`}>
      {categoryId ? (
        <Link
          to="/spending"
          search={{ month: cell.month, category: categoryId }}
          aria-label={`${b.openCell(name, monthLabel(cell.month))} · ${formatEurWhole(cell.spent)}${
            cell.status === "none" ? "" : ` · ${b.status[cell.status]}`
          }`}
          title={cell.status === "none" ? undefined : b.status[cell.status]}
          className="block rounded px-1 py-1 hover:underline"
        >
          {content}
        </Link>
      ) : (
        <span className="block px-1 py-1">{content}</span>
      )}
    </td>
  );
}

/** A category's monthly target (or objective), from a month on (F-BUD-1, 9). */
function TargetEditor({
  category,
  target,
  onDone,
}: {
  category: SpendingCategoryOut;
  /** The target in force this month. */
  target: string | null;
  onDone: (message: string) => void;
}) {
  const { t } = useI18n();
  const e = t.spendingBudget.editor;
  const queryClient = useQueryClient();
  const id = useId();
  const current = thisMonth();
  const targets = useQuery(targetsQuery);
  const history = (targets.data ?? [])
    .filter((x) => x.category_id === category.id)
    .sort((a, b) => a.from_month.localeCompare(b.from_month));
  const [amount, setAmount] = useState(target ? amountInputShort(target) : "");
  const [from, setFrom] = useState(current);
  const [error, setError] = useState<string | null>(null);

  const write = async (value: string | null) => {
    setError(null);
    try {
      await setTarget({
        path: { category_id: category.id, month: from },
        body: { amount: value },
        throwOnError: true,
      });
      await refreshSpending(queryClient);
      onDone(e.saved);
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = parseEurInput(amount);
    if (value === null || value.startsWith("-") || isZero(value)) {
      setError(e.invalid);
      return;
    }
    void write(value);
  };

  const remove = async (month: string) => {
    setError(null);
    try {
      await removeTarget({ path: { category_id: category.id, month }, throwOnError: true });
      await refreshSpending(queryClient);
      // The amount shown may be the one just removed: close rather than offer it again.
      onDone(e.removed);
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    }
  };

  return (
    <form
      onSubmit={submit}
      aria-label={
        category.kind === "savings" ? e.objectiveTitle(category.name) : e.title(category.name)
      }
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4"
    >
      <h2 className="font-semibold">
        {category.kind === "savings" ? e.objectiveTitle(category.name) : e.title(category.name)}
      </h2>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-amount`} className="text-sm font-medium">
            {e.amount}
          </label>
          <input
            id={`${id}-amount`}
            inputMode="decimal"
            value={amount}
            onChange={(ev) => setAmount(ev.target.value)}
            className={`${field} w-32 text-right font-mono`}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-from`} className="text-sm font-medium">
            {e.from}
          </label>
          <input
            id={`${id}-from`}
            type="month"
            required
            value={from}
            aria-describedby={`${id}-from-hint`}
            onChange={(ev) => ev.target.value && setFrom(ev.target.value)}
            className={field}
          />
        </div>
        <Button type="submit">{e.save}</Button>
        <Button variant="ghost" onClick={() => void write(null)}>
          {e.none}
        </Button>
        <Button variant="ghost" onClick={() => onDone("")}>
          {t.common.cancel}
        </Button>
      </div>
      <p id={`${id}-from-hint`} className="text-xs text-muted">
        {from < current ? e.pastNote(monthLabel(from)) : e.fromHint}
      </p>
      <ErrorAlert message={error} />
      {history.length > 0 && (
        <div className="flex flex-col gap-1 text-sm">
          <h3 className="font-medium">{e.history}</h3>
          <ul className="flex flex-col gap-1">
            {history.map((x) => (
              <li key={x.from_month} className="flex items-center gap-3">
                <span>
                  {x.amount === null
                    ? e.noneFrom(monthLabel(x.from_month))
                    : e.fromMonth(monthLabel(x.from_month), formatEurWhole(x.amount))}
                </span>
                <Button
                  variant="ghost"
                  className="px-2 py-0.5 text-xs"
                  aria-label={e.remove(monthLabel(x.from_month))}
                  onClick={() => void remove(x.from_month)}
                >
                  {t.common.delete}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </form>
  );
}
