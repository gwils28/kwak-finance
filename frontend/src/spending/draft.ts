/**
 * A grid row as typed (F-ENT-1): amounts as the user writes them, positive when spent, put
 * aside or received. The API stores them signed, negative for an outflow, so every amount but
 * an income line's is negated on the way in and out.
 */
import type { LineIn, LineOut, SpendingCategoryOut } from "../api/generated";
import { amountInputShort, isZero, parseEurInput } from "../lib/money";
import { daysInMonth } from "../lib/months";

export type SplitDraft = {
  /** Every part but the last. */
  parts: { category: string; amount: string }[];
  /** The last part's category: it takes the rest. */
  rest: string;
};

export type Draft = {
  day: string;
  label: string;
  amount: string;
  /** A category id, "" when none is chosen yet or the line is split. */
  category: string;
  split: SplitDraft | null;
};

export type Cell = "day" | "label" | "amount" | "category";

export function negate(amount: string): string {
  return amount.startsWith("-") ? amount.slice(1) : `-${amount}`;
}

/** The income categories: their lines are inflows, typed and stored positive. */
export type IncomeIds = ReadonlySet<string>;

export function incomeIds(categories: Pick<SpendingCategoryOut, "id" | "kind">[]): IncomeIds {
  return new Set(categories.filter((c) => c.kind === "income").map((c) => c.id));
}

/** A line is income or spending, never both: its last part's category says which. */
export function isIncomeLine(
  line: Pick<LineOut, "category_id" | "parts">,
  income: IncomeIds,
): boolean {
  const category = line.category_id ?? line.parts.at(-1)?.category_id;
  return category !== undefined && income.has(category);
}

/** A stored amount as the grid shows it: positive when spent, put aside or received. */
export function typedOf(amount: string, income: boolean): string {
  return income ? amount : negate(amount);
}

/** The typed amount as the API stores it; null when not a non-zero number of cents. */
function stored(typed: string, income = false): string | null {
  const amount = parseEurInput(typed);
  return amount === null || isZero(amount) ? null : typedOf(amount, income);
}

function splitComplete(split: SplitDraft): boolean {
  return Boolean(split.rest) && split.parts.every((p) => p.category && stored(p.amount) !== null);
}

/** The first cell to fill before the row can be saved, in the grid's order. */
export function firstMissing(draft: Draft): Cell | null {
  if (!draft.day) return "day";
  if (!draft.label.trim()) return "label";
  if (stored(draft.amount) === null) return "amount";
  if (draft.split ? !splitComplete(draft.split) : !draft.category) return "category";
  return null;
}

/** What the API takes, or null while the row is incomplete. */
export function lineBody(
  draft: Draft,
  income: IncomeIds,
  fixedExpenseId: string | null = null,
): LineIn | null {
  const inflow = income.has(draft.split ? draft.split.rest : draft.category);
  const amount = stored(draft.amount, inflow);
  if (firstMissing(draft) !== null || amount === null) return null;
  const common = { day: draft.day, label: draft.label.trim(), amount };
  if (!draft.split) {
    return { ...common, category_id: draft.category, fixed_expense_id: fixedExpenseId };
  }
  return {
    ...common,
    split: {
      parts: draft.split.parts.map((p) => ({
        category_id: p.category,
        amount: stored(p.amount, inflow) ?? "",
      })),
      rest_category_id: draft.split.rest,
    },
    fixed_expense_id: fixedExpenseId,
  };
}

/** A saved line, as the grid shows it for editing. */
export function draftOf(
  line: Pick<LineOut, "day" | "label" | "amount" | "category_id" | "parts">,
  income: IncomeIds,
): Draft {
  const inflow = isIncomeLine(line, income);
  const typed = (amount: string) => amountInputShort(typedOf(amount, inflow));
  const last = line.parts.at(-1);
  return {
    day: line.day,
    label: line.label,
    amount: typed(line.amount),
    category: line.category_id ?? "",
    split:
      line.parts.length > 0 && last
        ? {
            parts: line.parts
              .slice(0, -1)
              .map((p) => ({ category: p.category_id, amount: typed(p.amount) })),
            rest: last.category_id,
          }
        : null,
  };
}

/**
 * A new row's date (F-ENT-1): the last one used in this session when it is in the month,
 * otherwise today in the current month, the last day of a past month, the first of a later one.
 */
export function defaultDay(month: string, today: string, sessionDay: string | null): string {
  if (sessionDay?.startsWith(`${month}-`)) return sessionDay;
  const current = today.slice(0, 7);
  if (month === current) return today;
  if (month < current) return `${month}-${String(daysInMonth(month)).padStart(2, "0")}`;
  return `${month}-01`;
}
