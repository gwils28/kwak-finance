import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import type { SpendingCategoryOut } from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEur, fromCents, parseEurInput, toCents } from "../lib/money";
import { type Cell, type Draft, firstMissing, incomeIds, type SplitDraft } from "./draft";
import { byKind, labelsQuery } from "./queries";

const SPLIT = "__split";
/**
 * Below 640 px the grid's rows become cards (the same cells, laid out again): the label and
 * the amount first, the date and the category under them, the row's actions at the end.
 */
export const CARD = {
  table: "max-sm:block",
  head: "max-sm:hidden",
  body: "max-sm:block",
  row: "max-sm:grid max-sm:grid-cols-[1.25rem_minmax(0,1fr)_7.5rem_auto] max-sm:items-center max-sm:gap-x-1 max-sm:py-2",
  lead: "max-sm:col-start-1 max-sm:row-start-1 max-sm:w-auto",
  label: "max-sm:col-start-2 max-sm:row-start-1",
  amount: "max-sm:col-start-3 max-sm:row-start-1 max-sm:w-auto max-sm:font-semibold",
  side: "max-sm:col-start-4 max-sm:row-start-1",
  below: "max-sm:col-span-full max-sm:row-start-3",
  date: "max-sm:col-start-2 max-sm:row-start-2 max-sm:w-auto max-sm:text-xs max-sm:text-muted",
  category: "max-sm:col-span-2 max-sm:col-start-3 max-sm:row-start-2 max-sm:w-auto max-sm:text-xs",
  full: "max-sm:block",
} as const;

/** On a phone the empty row has no column headers above it: its fields show their edges. */
const NEW_CELL = "max-sm:border-border";

const CELL =
  "w-full rounded border border-transparent bg-transparent px-2 py-1 hover:border-border focus:border-accent focus:bg-surface focus-visible:outline-none";

/** Case and accents ignored, as the label memory compares labels (F-ENT-3). */
export function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

export function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

const same = (a: Draft, b: Draft) => JSON.stringify(a) === JSON.stringify(b);

export function CategoryOptions({ categories }: { categories: SpendingCategoryOut[] }) {
  const { t } = useI18n();
  const { expense, savings, income } = byKind(categories);
  const g = t.spending.grid;
  // An empty group would end the list on a bare heading, as if it were cut off.
  return (
    <>
      {(
        [
          [g.expenses, expense],
          [g.savings, savings],
          [g.income, income],
        ] as const
      )
        .filter(([, group]) => group.length > 0)
        .map(([label, group]) => (
          <optgroup key={label} label={label}>
            {group.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </optgroup>
        ))}
    </>
  );
}

type Props = {
  initial: Draft;
  categories: SpendingCategoryOut[];
  /** A saved line, the empty row, or a fixed expense's occurrence to confirm. */
  variant: "line" | "new" | "fixed";
  /** Saves the row; rejects with the API's error to show it. */
  onSave: (draft: Draft) => Promise<void>;
  /** The cell to focus when the row appears. */
  focus?: Cell;
  /** Before the date: the last-entry marker, a status… */
  lead?: ReactNode;
  actions?: ReactNode;
  /** The line just added: brought into view and marked. */
  highlight?: boolean;
};

/**
 * One row of the grid, every cell editable in place (F-ENT-1). Enter saves it once complete,
 * Escape puts it back as it was; a split line opens its parts below it (F-LIN-4).
 */
export function LineRow({
  initial,
  categories,
  variant,
  onSave,
  focus,
  lead,
  actions,
  highlight = false,
}: Props) {
  const { t } = useI18n();
  const g = t.spending.grid;
  const [base, setBase] = useState(initial);
  const [draft, setDraft] = useState(initial);
  const [categoryTouched, setCategoryTouched] = useState(false);
  const [labelTyped, setLabelTyped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [amountFocused, setAmountFocused] = useState(false);
  const row = useRef<HTMLTableRowElement>(null);
  useEffect(() => {
    if (highlight) row.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [highlight]);
  // Enter repeats faster than a save returns: one save at a time, or the line comes twice.
  const inFlight = useRef(false);
  const cells = useRef<Partial<Record<Cell, HTMLInputElement | HTMLSelectElement | null>>>({});
  const listId = useId();
  const dirty = !same(base, draft);

  // Fresh data from the server replaces the row, unless it holds changes not saved yet.
  const [seen, setSeen] = useState(initial);
  if (!same(seen, initial)) {
    setSeen(initial);
    if (!dirty) {
      setBase(initial);
      setDraft(initial);
    }
  }

  useEffect(() => {
    if (focus) cells.current[focus]?.focus();
  }, [focus]);

  const query = useDebounced(labelTyped ? draft.label : "", 200);
  const suggestions = useQuery(labelsQuery(query));

  // A known label typed or chosen brings its category of last time, never the amount.
  useEffect(() => {
    // A saved line keeps its category: only a row without one takes it from the label.
    if (!labelTyped || categoryTouched || draft.split || (variant === "line" && base.category)) {
      return;
    }
    const known = suggestions.data?.find((s) => fold(s.label) === fold(draft.label));
    if (known?.category_id && known.category_id !== draft.category) {
      setDraft((d) => ({ ...d, category: known.category_id ?? d.category }));
    }
  }, [
    suggestions.data,
    draft.label,
    draft.category,
    draft.split,
    labelTyped,
    categoryTouched,
    variant,
    base.category,
  ]);

  const set = (changes: Partial<Draft>) => {
    setError(null);
    setDraft((d) => ({ ...d, ...changes }));
  };

  // Back to the line as the server last sent it.
  const reset = () => {
    setBase(seen);
    setDraft(seen);
    setError(null);
    setCategoryTouched(false);
    setLabelTyped(false);
  };

  const save = async () => {
    if ((variant === "line" && !dirty) || inFlight.current) return;
    const missing = firstMissing(draft);
    if (missing) {
      if (missing === "amount" && draft.amount.trim()) setError(g.amountInvalid);
      cells.current[missing]?.focus();
      return;
    }
    inFlight.current = true;
    setSaving(true);
    try {
      await onSave(draft);
      setBase(draft);
      setCategoryTouched(false);
      setLabelTyped(false);
    } catch (exc) {
      setError(detailSentence(exc) ?? t.errors.generic);
    } finally {
      inFlight.current = false;
      setSaving(false);
    }
  };

  const onKeyDown = (event: KeyboardEvent) => {
    const target = event.target as HTMLElement;
    if (event.key === "Enter" && target.tagName !== "BUTTON") {
      event.preventDefault();
      void save();
    } else if (event.key === "Escape") {
      event.preventDefault();
      reset();
    }
  };

  const chooseCategory = (value: string) => {
    setCategoryTouched(true);
    if (value === SPLIT) {
      set({ category: "", split: { parts: [{ category: draft.category, amount: "" }], rest: "" } });
    } else {
      set({ category: value, split: null });
    }
  };

  const greyed = variant === "fixed" && !dirty;
  const look = `${greyed ? "text-muted italic" : ""} ${dirty || highlight ? "bg-accent/10" : ""}`;
  // Out of the amount cell, the amount reads as money; an income keeps its sign and its colour.
  const parsed = amountFocused ? null : parseEurInput(draft.amount);
  const income = incomeIds(categories).has(draft.split ? draft.split.rest : draft.category);
  const shownAmount = parsed === null ? null : income ? `+${formatEur(parsed)}` : formatEur(parsed);

  return (
    <>
      <tr
        ref={row}
        className={`border-t border-border align-middle transition-colors ${CARD.row} ${look}`}
        data-dirty={dirty || undefined}
        onKeyDown={onKeyDown}
      >
        <td className={`w-8 px-1 text-center ${CARD.lead}`}>{lead}</td>
        <td className={`w-40 py-1 ${CARD.date}`}>
          <input
            ref={(el) => {
              cells.current.day = el;
            }}
            type="date"
            aria-label={g.date}
            value={draft.day}
            onChange={(e) => set({ day: e.target.value })}
            className={CELL}
          />
        </td>
        <td className={`py-1 ${CARD.label}`}>
          <input
            ref={(el) => {
              cells.current.label = el;
            }}
            aria-label={g.label}
            placeholder={variant === "new" ? g.label : undefined}
            value={draft.label}
            maxLength={100}
            list={listId}
            autoComplete="off"
            onChange={(e) => {
              setLabelTyped(true);
              set({ label: e.target.value });
            }}
            className={`${CELL} ${variant === "new" ? NEW_CELL : ""}`}
          />
          <datalist id={listId}>
            {suggestions.data?.map((s) => (
              <option key={s.label} value={s.label} />
            ))}
          </datalist>
        </td>
        <td className={`relative w-32 py-1 ${CARD.amount}`}>
          <input
            ref={(el) => {
              cells.current.amount = el;
            }}
            aria-label={g.amount}
            placeholder={variant === "new" ? g.amount : undefined}
            inputMode="decimal"
            value={draft.amount}
            onChange={(e) => set({ amount: e.target.value })}
            onFocus={() => setAmountFocused(true)}
            onBlur={() => setAmountFocused(false)}
            className={`${CELL} text-right font-mono tabular-nums ${shownAmount === null ? "" : "text-transparent"} ${variant === "new" ? NEW_CELL : ""}`}
          />
          {shownAmount !== null && (
            <span
              aria-hidden="true"
              className={`pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 font-mono tabular-nums ${income ? "text-positive" : ""}`}
            >
              {shownAmount}
            </span>
          )}
        </td>
        <td className={`w-48 py-1 ${CARD.category}`}>
          <select
            ref={(el) => {
              cells.current.category = el;
            }}
            aria-label={g.category}
            value={draft.split ? SPLIT : draft.category}
            onChange={(e) => chooseCategory(e.target.value)}
            className={CELL}
          >
            <option value="" disabled>
              {g.chooseCategory}
            </option>
            <CategoryOptions categories={categories} />
            <option value={SPLIT}>{g.split}</option>
          </select>
        </td>
        {/* Save and cancel, or a fixed expense's buttons, take a line of their own on a card. */}
        <td
          className={`py-1 pl-2 whitespace-nowrap ${dirty || variant === "fixed" ? CARD.below : CARD.side}`}
        >
          <div className="flex items-center justify-end gap-2">
            {dirty && variant !== "fixed" && (
              <>
                <span className="sr-only">{g.unsaved}</span>
                <Button onClick={() => void save()} disabled={saving} className="py-1">
                  {t.common.save}
                </Button>
                <Button variant="ghost" onClick={reset} className="py-1">
                  {t.common.cancel}
                </Button>
              </>
            )}
            {variant === "fixed" && (
              <Button onClick={() => void save()} disabled={saving} className="py-1">
                {t.spending.fixed.confirm}
              </Button>
            )}
            {actions}
          </div>
        </td>
      </tr>
      {draft.split && (
        <SplitRow
          split={draft.split}
          amount={draft.amount}
          categories={categories}
          onChange={(split) => set({ split })}
          onRemove={() =>
            set({
              category: draft.split?.parts[0]?.category || draft.split?.rest || "",
              split: null,
            })
          }
          onKeyDown={onKeyDown}
        />
      )}
      {error && (
        <tr className={CARD.full}>
          <td className="max-sm:hidden" />
          <td colSpan={5} role="alert" className={`pb-2 text-sm text-negative ${CARD.full}`}>
            {error}
          </td>
        </tr>
      )}
    </>
  );
}

/** The parts of a split line: every part but the last, which takes the rest (F-LIN-4). */
function SplitRow({
  split,
  amount,
  categories,
  onChange,
  onRemove,
  onKeyDown,
}: {
  split: SplitDraft;
  amount: string;
  categories: SpendingCategoryOut[];
  onChange: (split: SplitDraft) => void;
  onRemove: () => void;
  onKeyDown: (event: KeyboardEvent) => void;
}) {
  const { t } = useI18n();
  const s = t.spending.split;
  const cents = (typed: string) => {
    const value = parseEurInput(typed);
    return value === null ? null : toCents(value);
  };
  const total = cents(amount);
  const given = split.parts.map((p) => cents(p.amount));
  const rest =
    total === null || given.some((c) => c === null)
      ? null
      : given.reduce<number>((sum, c) => sum - (c ?? 0), total);
  const setPart = (index: number, changes: Partial<SplitDraft["parts"][number]>) =>
    onChange({
      ...split,
      parts: split.parts.map((p, i) => (i === index ? { ...p, ...changes } : p)),
    });

  return (
    <tr onKeyDown={onKeyDown} className={CARD.full}>
      <td className="max-sm:hidden" />
      <td colSpan={5} className={`pb-2 ${CARD.full}`}>
        <fieldset className="flex flex-col gap-1 rounded-md border border-border p-2 text-sm">
          <legend className="px-1 text-muted">{s.title}</legend>
          {split.parts.map((part, index) => (
            // biome-ignore lint/suspicious/noArrayIndexKey: parts have no identity of their own
            <div key={index} className="flex flex-wrap items-center gap-2">
              <span className="w-16 text-muted">{s.part(index + 1)}</span>
              <select
                aria-label={s.partCell(index + 1, t.spending.grid.category)}
                value={part.category}
                onChange={(e) => setPart(index, { category: e.target.value })}
                className={`${CELL} w-48 border-border`}
              >
                <option value="" disabled>
                  {t.spending.grid.chooseCategory}
                </option>
                <CategoryOptions categories={categories} />
              </select>
              <input
                aria-label={s.partCell(index + 1, t.spending.grid.amount)}
                inputMode="decimal"
                value={part.amount}
                onChange={(e) => setPart(index, { amount: e.target.value })}
                className={`${CELL} w-28 border-border text-right font-mono tabular-nums`}
              />
              {split.parts.length > 1 && (
                <Button
                  variant="ghost"
                  className="py-1"
                  onClick={() =>
                    onChange({ ...split, parts: split.parts.filter((_, i) => i !== index) })
                  }
                >
                  {s.removePart}
                </Button>
              )}
            </div>
          ))}
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-16 text-muted">{s.restPart}</span>
            <select
              aria-label={s.restCell(t.spending.grid.category)}
              value={split.rest}
              onChange={(e) => onChange({ ...split, rest: e.target.value })}
              className={`${CELL} w-48 border-border`}
            >
              <option value="" disabled>
                {t.spending.grid.chooseCategory}
              </option>
              <CategoryOptions categories={categories} />
            </select>
            {rest !== null && (
              <span className={rest > 0 ? "text-muted" : "text-negative"}>
                {s.restAmount(formatEur(fromCents(rest)))}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <Button
              variant="ghost"
              className="py-1"
              onClick={() =>
                onChange({ ...split, parts: [...split.parts, { category: "", amount: "" }] })
              }
            >
              {s.addPart}
            </Button>
            <Button variant="ghost" className="py-1" onClick={onRemove}>
              {s.remove}
            </Button>
          </div>
        </fieldset>
      </td>
    </tr>
  );
}
