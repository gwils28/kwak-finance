import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getRouteApi, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  createLine,
  deleteLine,
  type FixedOccurrenceOut,
  type LineOut,
  replaceLine,
  type SpendingCategoryOut,
  skipOccurrence,
  unskipOccurrence,
} from "../api/generated";
import { detailSentence } from "../auth/errors";
import { HelpLink } from "../components/HelpLink";
import { Icon } from "../components/icons";
import { Button, ErrorAlert } from "../components/ui";
import { useI18n } from "../i18n";
import { formatDate, formatInstantDay, formatShortDay, todayIso } from "../lib/dates";
import { amountInputShort, formatEur } from "../lib/money";
import { isMonth, monthLabel, shiftMonth, thisMonth } from "../lib/months";
import {
  type Cell,
  type Draft,
  defaultDay,
  draftOf,
  type IncomeIds,
  incomeIds,
  lineBody,
  negate,
} from "./draft";
import { CARD, LineRow } from "./LineRow";
import { QuickLine } from "./QuickLine";
import {
  linesQuery,
  occurrencesQuery,
  refreshSpending,
  spendingCategoriesQuery,
  summaryQuery,
} from "./queries";

export type GridSearch = { month?: string; category?: string };

/** Search params of /spending, validated: anything malformed is dropped. */
export function parseGridSearch(search: Record<string, unknown>): GridSearch {
  return {
    month: typeof search.month === "string" && isMonth(search.month) ? search.month : undefined,
    category: typeof search.category === "string" && search.category ? search.category : undefined,
  };
}

const route = getRouteApi("/app/spending");

type Notice = { text: string; month?: string; undo?: () => Promise<void> };

const empty = (day: string): Draft => ({ day, label: "", amount: "", category: "", split: null });

const inCategory = (line: LineOut, category: string) =>
  line.category_id === category || line.parts.some((p) => p.category_id === category);

/** The Spending space's main page (F-ENT-1): one month of lines, entered at the keyboard. */
export function GridPage() {
  const { t } = useI18n();
  const g = t.spending.grid;
  const search = route.useSearch();
  const navigate = route.useNavigate();
  const queryClient = useQueryClient();
  const current = thisMonth();
  const month = search.month ?? current;
  const categories = useQuery(spendingCategoriesQuery);
  const lines = useQuery(linesQuery(month));
  const occurrences = useQuery(occurrencesQuery(month));
  const [sessionDay, setSessionDay] = useState<string | null>(null);
  const [newRow, setNewRow] = useState<{ key: number; draft: Draft | null; focus?: Cell }>({
    key: 0,
    draft: null,
  });
  const [notice, setNotice] = useState<Notice | null>(null);
  // The line just added is brought into view and marked a moment.
  const [justAdded, setJustAdded] = useState<string | null>(null);
  useEffect(() => {
    if (justAdded === null) return;
    const timer = setTimeout(() => setJustAdded(null), 3000);
    return () => clearTimeout(timer);
  }, [justAdded]);
  const [failure, setFailure] = useState<string | null>(null);
  const busy = useRef(false);
  const day = defaultDay(month, todayIso(), sessionDay);
  const income: IncomeIds = incomeIds(categories.data ?? []);

  const goTo = (target: string) => {
    setNotice(null);
    setFailure(null);
    setNewRow((row) => ({ key: row.key + 1, draft: null }));
    void navigate({
      search: (prev) => ({ ...prev, month: target === current ? undefined : target }),
    });
  };

  // The previous and next months are a key away, wherever the focus is.
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if (!event.altKey || (event.key !== "PageUp" && event.key !== "PageDown")) return;
      event.preventDefault();
      // A row with changes not saved keeps the month: Enter or Escape first.
      if ((event.target as Element | null)?.closest?.("[data-dirty]")) return;
      goTo(shiftMonth(month, event.key === "PageUp" ? -1 : 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const create = async (draft: Draft, fixedId: string | null = null) => {
    const body = lineBody(draft, income, fixedId);
    if (!body) return;
    const { data: added } = await createLine({ body, throwOnError: true });
    setSessionDay(draft.day);
    const where = draft.day.slice(0, 7);
    if (where === month) {
      setJustAdded(added.id);
      setNotice({
        text: g.added(added.label),
        undo: () =>
          attempt(async () => {
            await deleteLine({ path: { line_id: added.id }, throwOnError: true });
            setNotice(null);
            await refreshSpending(queryClient);
          }),
      });
    } else {
      setNotice({ text: t.spending.quick.savedElsewhere(monthLabel(where)), month: where });
    }
    await refreshSpending(queryClient);
  };

  /** One write at a time, its failure said rather than lost: a double click acts once. */
  const attempt = async (write: () => Promise<void>) => {
    if (busy.current) return;
    busy.current = true;
    setFailure(null);
    try {
      await write();
    } catch (exc) {
      setFailure(detailSentence(exc) ?? t.errors.generic);
    } finally {
      busy.current = false;
    }
  };

  const remove = (line: LineOut) =>
    attempt(async () => {
      await deleteLine({ path: { line_id: line.id }, throwOnError: true });
      const body = lineBody(draftOf(line, income), income, line.fixed_expense_id);
      setNotice({
        text: g.deleted(line.label),
        undo: body
          ? () =>
              attempt(async () => {
                await createLine({ body, throwOnError: true });
                setNotice(null);
                await refreshSpending(queryClient);
              })
          : undefined,
      });
      await refreshSpending(queryClient);
    });

  if (!categories.data || !lines.data) return <p>{t.common.loading}</p>;
  const filter = categories.data.find((c) => c.id === search.category);
  const shown = filter
    ? lines.data.lines.filter((l) => inCategory(l, filter.id))
    : lines.data.lines;
  const last = lines.data.last_entry;
  const pending = (occurrences.data ?? []).filter(
    (o) => o.status !== "confirmed" && (!filter || o.category_id === filter.id),
  );

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-2 text-2xl font-black tracking-tight sm:text-3xl">
            {t.spending.title}
          </h1>
          <HelpLink section="lines" />
          {/* The month and its arrows hold together on one line, even on a phone. */}
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              aria-label={t.spending.previousMonth}
              aria-keyshortcuts="Alt+PageUp"
              title={t.spending.monthKeys}
              onClick={() => goTo(shiftMonth(month, -1))}
            >
              ‹
            </Button>
            <h2 className="min-w-28 text-center text-lg font-bold whitespace-nowrap capitalize sm:min-w-32 sm:text-xl">
              {monthLabel(month)}
            </h2>
            <Button
              variant="ghost"
              aria-label={t.spending.nextMonth}
              aria-keyshortcuts="Alt+PageDown"
              title={t.spending.monthKeys}
              onClick={() => goTo(shiftMonth(month, 1))}
            >
              ›
            </Button>
          </div>
          {month !== current && (
            <Button variant="ghost" onClick={() => goTo(current)}>
              {t.spending.thisMonth}
            </Button>
          )}
        </div>
        <Link
          to="/spending/fixed"
          className="rounded-md border border-border bg-surface px-3 py-2 text-sm hover:border-accent"
        >
          {t.spending.fixedLink}
        </Link>
      </div>

      <MonthFigures month={month} />

      {last && (
        <p className="text-sm text-muted">
          {t.spending.lastEntry(formatShortDay(last.day), formatInstantDay(last.entered_at))}
          {!last.day.startsWith(month) && (
            <>
              {" · "}
              <button
                type="button"
                className="text-accent underline"
                onClick={() => goTo(last.day.slice(0, 7))}
              >
                {t.spending.goToMonth(monthLabel(last.day.slice(0, 7)))}
              </button>
            </>
          )}
        </p>
      )}

      <QuickLine
        categories={categories.data}
        defaultDay={day}
        onCreate={(draft) => create(draft)}
        onIncomplete={(draft, focus) => setNewRow((row) => ({ key: row.key + 1, draft, focus }))}
      />

      <ErrorAlert message={failure} />
      {notice && (
        <p
          className="flex flex-wrap items-center gap-3 rounded-md border border-accent px-3 py-2 text-sm"
          aria-live="polite"
        >
          {notice.text}
          {notice.month && (
            <button
              type="button"
              className="text-accent underline"
              onClick={() => notice.month && goTo(notice.month)}
            >
              {t.spending.goToMonth(monthLabel(notice.month))}
            </button>
          )}
          {notice.undo && (
            <Button variant="ghost" className="py-1" onClick={() => void notice.undo?.()}>
              {g.undo}
            </Button>
          )}
        </p>
      )}

      {filter && (
        <p className="flex items-center gap-3 text-sm">
          <span className="rounded-full border border-accent px-3 py-1">
            {g.filtered(filter.name)}
          </span>
          <button
            type="button"
            className="text-accent underline"
            onClick={() => void navigate({ search: (prev) => ({ ...prev, category: undefined }) })}
          >
            {g.showAll}
          </button>
        </p>
      )}

      {/* Positioned, so the sr-only header text is clipped with the table, not widening the page. */}
      <div className="relative overflow-x-auto">
        <table
          className={`w-full text-sm sm:min-w-[44rem] ${CARD.table}`}
          aria-label={g.caption(monthLabel(month))}
        >
          <thead className={CARD.head}>
            <tr className="text-left text-muted">
              <th className="w-8" />
              <th className="px-2 py-2 font-medium">{g.date}</th>
              <th className="px-2 py-2 font-medium">{g.label}</th>
              <th className="px-2 py-2 text-right font-medium">{g.amount}</th>
              <th className="px-2 py-2 font-medium">{g.category}</th>
              <th className="px-2 py-2 text-right font-medium">
                <span className="sr-only">{g.actions}</span>
              </th>
            </tr>
          </thead>
          {pending.length > 0 && (
            <tbody aria-label={t.spending.fixed.toConfirmCaption} className={CARD.body}>
              <tr className={CARD.full}>
                <th
                  colSpan={6}
                  className={`px-2 pt-3 pb-1 text-left text-xs font-semibold text-muted uppercase ${CARD.full}`}
                >
                  {t.spending.fixed.toConfirm}
                </th>
              </tr>
              {pending.map((o) => (
                <Occurrence
                  key={`${o.fixed_expense_id}-${o.due}`}
                  occurrence={o}
                  month={month}
                  categories={categories.data}
                  onConfirm={(draft) => create(draft, o.fixed_expense_id)}
                  onToggle={(write) => attempt(write)}
                />
              ))}
            </tbody>
          )}
          <tbody className={CARD.body}>
            {shown.map((line) => (
              <LineRow
                key={line.id}
                variant="line"
                initial={draftOf(line, income)}
                categories={categories.data}
                highlight={line.id === justAdded}
                lead={
                  line.id === last?.id ? (
                    <span
                      role="img"
                      aria-label={t.spending.lastEntryMarker}
                      title={t.spending.lastEntryMarker}
                      className="text-accent"
                    >
                      ●
                    </span>
                  ) : null
                }
                onSave={async (draft) => {
                  const body = lineBody(draft, income, line.fixed_expense_id);
                  if (!body) return;
                  await replaceLine({ path: { line_id: line.id }, body, throwOnError: true });
                  setSessionDay(draft.day);
                  await refreshSpending(queryClient);
                }}
                actions={
                  <button
                    type="button"
                    aria-label={`${t.common.delete} ${line.label}`}
                    title={t.common.delete}
                    onClick={() => void remove(line)}
                    className="rounded p-1.5 text-muted hover:bg-border hover:text-negative focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    <Icon name="trash" className="size-4" />
                  </button>
                }
              />
            ))}
          </tbody>
          <tbody aria-label={g.newRow} className={CARD.body}>
            <LineRow
              key={`${month}-${newRow.key}`}
              variant="new"
              initial={newRow.draft ?? empty(day)}
              focus={newRow.focus}
              categories={categories.data}
              lead={<span className="text-muted">+</span>}
              onSave={async (draft) => {
                await create(draft);
                setNewRow((row) => ({
                  key: row.key + 1,
                  draft: empty(defaultDay(month, todayIso(), draft.day)),
                  focus: "label",
                }));
              }}
            />
          </tbody>
        </table>
      </div>
      <p className="flex flex-wrap justify-between gap-2 text-xs text-muted">
        <span>{g.keys}</span>
        <span>{g.count(shown.length)}</span>
      </p>
    </div>
  );
}

/** A fixed expense due this month (F-FIX-2): greyed until confirmed, or skipped. */
function Occurrence({
  occurrence,
  month,
  categories,
  onConfirm,
  onToggle,
}: {
  occurrence: FixedOccurrenceOut;
  month: string;
  categories: SpendingCategoryOut[];
  onConfirm: (draft: Draft) => Promise<void>;
  /** Runs a skip or its undo, saying when it fails. */
  onToggle: (write: () => Promise<void>) => Promise<void>;
}) {
  const { t } = useI18n();
  const f = t.spending.fixed;
  const queryClient = useQueryClient();
  const path = { fixed_id: occurrence.fixed_expense_id, month };
  const toggle = (skip: boolean) =>
    onToggle(async () => {
      await (skip ? skipOccurrence : unskipOccurrence)({ path, throwOnError: true });
      await refreshSpending(queryClient);
    });

  if (occurrence.status === "skipped") {
    return (
      <tr className={`border-t border-border text-muted ${CARD.row}`}>
        <td className="max-sm:hidden" />
        <td className={`px-2 py-1 ${CARD.date}`}>{formatDate(occurrence.due)}</td>
        <td className={`px-2 py-1 line-through ${CARD.label}`}>{occurrence.label}</td>
        <td className={`px-2 py-1 text-right font-mono tabular-nums line-through ${CARD.amount}`}>
          {formatEur(negate(occurrence.amount))}
        </td>
        <td className={`px-2 py-1 ${CARD.category}`}>{f.skipped}</td>
        <td className={`px-2 py-1 text-right ${CARD.below}`}>
          <Button variant="ghost" className="py-1" onClick={() => void toggle(false)}>
            {f.unskip}
          </Button>
        </td>
      </tr>
    );
  }
  return (
    <LineRow
      variant="fixed"
      initial={{
        day: occurrence.due,
        label: occurrence.label,
        amount: amountInputShort(negate(occurrence.amount)),
        category: occurrence.category_id,
        split: null,
      }}
      categories={categories}
      onSave={onConfirm}
      actions={
        <Button
          variant="ghost"
          className="py-1 whitespace-nowrap"
          onClick={() => void toggle(true)}
        >
          {f.skip}
        </Button>
      }
    />
  );
}

/** The month's income (its income lines, F-INC-1), spent, saved and rest (F-DSH-4). */
function MonthFigures({ month }: { month: string }) {
  const { t } = useI18n();
  const s = t.spending;
  const summary = useQuery(summaryQuery(month));
  const figures = summary.data?.figures;
  const tile = "flex flex-col gap-1 rounded-lg border border-border bg-surface p-4";
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {(
        [
          ["income", s.income],
          ["spent", s.spent],
          ["saved", s.saved],
          ["rest", s.rest],
        ] as const
      ).map(([key, label]) => (
        <div key={key} className={tile}>
          <span className="text-sm text-muted">{label}</span>
          <span
            className={`text-lg tabular-nums ${
              key === "rest" && figures?.rest.startsWith("-") ? "text-negative" : ""
            }`}
          >
            {figures ? formatEur(figures[key]) : "…"}
          </span>
        </div>
      ))}
    </div>
  );
}
