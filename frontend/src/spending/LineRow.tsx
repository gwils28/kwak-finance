import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef, useState } from "react";
import type { SpendingCategoryOut } from "../api/generated";
import { detailSentence } from "../auth/errors";
import { Button } from "../components/ui";
import { useI18n } from "../i18n";
import { formatEur, fromCents, parseEurInput, toCents } from "../lib/money";
import { type Cell, type Draft, firstMissing, type SplitDraft } from "./draft";
import { byKind, labelsQuery } from "./queries";

const SPLIT = "__split";
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
  return (
    <>
      <optgroup label={t.spending.grid.expenses}>
        {expense.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </optgroup>
      <optgroup label={t.spending.grid.savings}>
        {savings.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </optgroup>
      <optgroup label={t.spending.grid.income}>
        {income.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </optgroup>
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
};

/**
 * One row of the grid, every cell editable in place (F-ENT-1). Enter saves it once complete,
 * Escape puts it back as it was; a split line opens its parts below it (F-LIN-4).
 */
export function LineRow({ initial, categories, variant, onSave, focus, lead, actions }: Props) {
  const { t } = useI18n();
  const g = t.spending.grid;
  const [base, setBase] = useState(initial);
  const [draft, setDraft] = useState(initial);
  const [categoryTouched, setCategoryTouched] = useState(false);
  const [labelTyped, setLabelTyped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
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
  const look = `${greyed ? "text-muted italic" : ""} ${dirty ? "bg-accent/10" : ""}`;

  return (
    <>
      <tr
        className={`border-t border-border align-middle ${look}`}
        data-dirty={dirty || undefined}
        onKeyDown={onKeyDown}
      >
        <td className="w-8 px-1 text-center">{lead}</td>
        <td className="w-40 py-1">
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
        <td className="py-1">
          <input
            ref={(el) => {
              cells.current.label = el;
            }}
            aria-label={g.label}
            value={draft.label}
            maxLength={100}
            list={listId}
            autoComplete="off"
            onChange={(e) => {
              setLabelTyped(true);
              set({ label: e.target.value });
            }}
            className={CELL}
          />
          <datalist id={listId}>
            {suggestions.data?.map((s) => (
              <option key={s.label} value={s.label} />
            ))}
          </datalist>
        </td>
        <td className="w-32 py-1">
          <input
            ref={(el) => {
              cells.current.amount = el;
            }}
            aria-label={g.amount}
            inputMode="decimal"
            value={draft.amount}
            onChange={(e) => set({ amount: e.target.value })}
            className={`${CELL} text-right font-mono tabular-nums`}
          />
        </td>
        <td className="w-48 py-1">
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
        <td className="py-1 pl-2 whitespace-nowrap">
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
        <tr>
          <td />
          <td colSpan={5} role="alert" className="pb-2 text-sm text-negative">
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
    <tr onKeyDown={onKeyDown}>
      <td />
      <td colSpan={5} className="pb-2">
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
