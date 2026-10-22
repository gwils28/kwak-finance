/** Synthetic spending data for the tests: a household's categories and one month of lines. */
import type {
  FixedOccurrenceOut,
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
export const salaries = category("c-salaries", "Salaries", 10, "income");
export const spendingCategories = [groceries, home, housing, savingsCategory, salaries];

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
  figures: { ...figures("3000.00", "99.90", "200.00", "2700.10"), savings_rate: "0.9667" },
  previous: figures("3000.00", "111.00", "0.00", "2889.00"),
  average: figures("3000.00", "90.00", "0.00", "2910.00"),
  changes: {
    vs_previous: { income: "0", spent: "-0.1000", saved: null, rest: "-0.0654" },
    vs_average: { income: "0", spent: "0.1100", saved: null, rest: "-0.0721" },
  },
  progress: {
    warn_at: "0.80",
    lines: [
      {
        category_id: "c-groceries",
        name: "Groceries",
        spent: "42.50",
        target: "50.00",
        remaining: "7.50",
        share: "0.8500",
        status: "watch",
        pace: "0.7097",
      },
    ],
  },
  cumulative: [
    { day: `${month}-01`, spent: "0.00" },
    { day: `${month}-02`, spent: "42.50" },
    { day: `${month}-03`, spent: "99.90" },
  ],
  target_total: "50.00",
  projected_rest: "1750.10",
  to_confirm: 1,
  top: [{ category_id: "c-home", spent: "57.40", share: "0.5746" }],
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
  };
}
