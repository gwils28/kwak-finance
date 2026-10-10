/** A budget matrix and plans as the API sends them, for the page's tests. */

import type { PlanOut } from "../api/generated";
import { shiftMonth, thisMonth } from "../lib/months";
import { monthsBetween, periodContaining, periodStart, periodText } from "../lib/plans";

const cell = (
  month: string,
  spent: string,
  target: string | null,
  status: string,
  gap: string | null = null,
  ratio: string | null = null,
) => ({
  month,
  spent,
  target,
  gap,
  gap_ratio: ratio,
  status,
});
const matrixMonths = ["2026-02", "2026-03"];
export const matrix = {
  months: matrixMonths,
  band: "0.05",
  rows: [
    {
      category_id: "c-food",
      name: "Food",
      parent_id: null,
      level: 0,
      target: "360.00",
      target_from_children: true,
      cells: [
        cell("2026-02", "300.00", "360.00", "under", "-60.00", "-0.1667"),
        cell("2026-03", "362.00", "360.00", "on", "2.00", "0.0056"),
      ],
    },
    {
      category_id: "c-bakery",
      name: "Bakery and coffee",
      parent_id: "c-food",
      level: 1,
      target: "60.00",
      cells: [
        cell("2026-02", "40.00", "60.00", "under", "-20.00", "-0.3333"),
        cell("2026-03", "72.00", "60.00", "over", "12.00", "0.2000"),
      ],
    },
    {
      category_id: "c-groceries",
      name: "Groceries",
      parent_id: "c-food",
      level: 1,
      target: null,
      cells: [cell("2026-02", "260.00", null, "none"), cell("2026-03", "290.00", null, "none")],
    },
    {
      category_id: "c-edu",
      name: "Education",
      parent_id: null,
      level: 0,
      target: null,
      cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "0.00", null, "none")],
    },
    {
      category_id: "c-books",
      name: "Books",
      parent_id: "c-edu",
      level: 1,
      target: null,
      cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "0.00", null, "none")],
    },
  ],
  uncategorised: {
    category_id: null,
    name: "To categorise",
    parent_id: null,
    level: 0,
    target: null,
    cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "25.50", null, "none")],
  },
  total: {
    category_id: null,
    name: "Total",
    parent_id: null,
    level: 0,
    target: "360.00",
    cells: [
      cell("2026-02", "300.00", "360.00", "under", "-60.00", "-0.1667"),
      cell("2026-03", "387.50", "360.00", "over", "27.50", "0.0764"),
    ],
  },
};

// Plans are built around the real current month, as the page reads it.
export const quarter = periodContaining("quarter", thisMonth());
export const start = periodStart(quarter);
export const months = monthsBetween(start, shiftMonth(start, 2));
export const currentLabel = `Q${quarter.number} ${quarter.year}`;

export const current = (changes: Partial<PlanOut> = {}): PlanOut => ({
  id: "p-current",
  period: periodText(quarter),
  kind: "quarter",
  start,
  end: months[2] as string,
  targets: [{ category_id: "c-bakery", amount: "60.00" }],
  expected_income: null,
  note: null,
  closed_early: false,
  close_reason: null,
  editable: true,
  ...changes,
});
