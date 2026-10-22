/** Synthetic spending data for the tests: a household's categories and one month of lines. */
import type {
  FixedOccurrenceOut,
  IncomeOut,
  LineOut,
  MonthLinesOut,
  SpendingCategoryOut,
  SpendingFiguresOut,
  SpendingMonthOut,
} from "../api/generated";

const category = (id: string, name: string, position: number, kind = "expense", one_off = false) =>
  ({ id, name, kind, one_off, position }) as SpendingCategoryOut;

export const groceries = category("c-groceries", "Groceries", 1);
export const home = category("c-home", "Home", 2);
export const housing = category("c-housing", "Housing", 0, "expense", true);
export const savingsCategory = category("c-savings", "Savings", 9, "savings");
export const spendingCategories = [groceries, home, housing, savingsCategory];

export const bakery: LineOut = {
  id: "l1",
  day: "2026-10-14",
  label: "Bakery",
  amount: "-12.50",
  category_id: groceries.id,
  parts: [],
  fixed_expense_id: null,
  entered_by: "Wilson",
  entered_at: "2026-10-15T08:00:00Z",
};

export const supermarket: LineOut = {
  ...bakery,
  id: "l2",
  day: "2026-10-16",
  label: "Supermarket",
  amount: "-87.40",
  category_id: null,
  parts: [
    { category_id: groceries.id, amount: "-30.00" },
    { category_id: home.id, amount: "-57.40" },
  ],
  entered_at: "2026-10-16T19:00:00Z",
};

export const monthOf = (month: string, lines: LineOut[]): MonthLinesOut => ({
  month,
  lines,
  last_entry: lines.length
    ? {
        id: lines.at(-1)?.id ?? "",
        day: lines.at(-1)?.day ?? "",
        entered_at: lines.at(-1)?.entered_at ?? "",
      }
    : null,
});

const figures = (
  income: string,
  spent: string,
  saved: string,
  rest: string,
): SpendingFiguresOut => ({
  income,
  spent,
  saved,
  rest,
  savings_rate: null,
});

export const summaryOf = (month: string): SpendingMonthOut => ({
  month,
  figures: figures("3000.00", "99.90", "0.00", "2900.10"),
  previous: figures("0", "0", "0", "0"),
  average: null,
  changes: {} as SpendingMonthOut["changes"],
  income_carried: false,
  progress: {} as SpendingMonthOut["progress"],
  projected_rest: "2900.10",
  to_confirm: 0,
  top: [],
});

export const incomeOf = (
  month: string,
  amount: string | null = "3000.00",
  carried = false,
): IncomeOut => ({
  month,
  amount,
  carried,
});

export const rent: FixedOccurrenceOut = {
  fixed_expense_id: "f-rent",
  label: "Rent",
  category_id: housing.id,
  due: "2026-10-05",
  amount: "-950.00",
  status: "to_confirm",
  line_id: null,
};

type Handler = (body: unknown, url: URL) => Response;

/** The handlers the grid needs, for `fakeApi`. */
export function spendingHandlers(
  lines: LineOut[] = [bakery, supermarket],
  occurrences: FixedOccurrenceOut[] = [],
): Record<string, Handler> {
  return {
    "GET /api/spending/categories": () => Response.json(spendingCategories),
    "GET /api/spending/lines": (_, url) =>
      Response.json(monthOf(url.searchParams.get("month") ?? "", lines)),
    "GET /api/spending/month": (_, url) =>
      Response.json(summaryOf(url.searchParams.get("month") ?? "")),
    "GET /api/spending/fixed/occurrences": () => Response.json(occurrences),
    "GET /api/spending/labels": () => Response.json([]),
    "GET /api/spending/income/2026-10": () => Response.json(incomeOf("2026-10")),
  };
}
