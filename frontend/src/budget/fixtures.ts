/** A budget matrix and plans as the API sends them, for the page's tests. */

import type {
  ComparisonOut,
  CumulativeOut,
  PlanOut,
  ReviewOut,
  ReviewRowOut,
} from "../api/generated";
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

// A plan review, as GET /api/budget/plans/{id}/review sends it.
const reviewRow = (changes: Partial<ReviewRowOut> & { name: string }): ReviewRowOut => ({
  category_id: `c-${changes.name.toLowerCase()}`,
  parent_id: null,
  level: 0,
  monthly_target: null,
  envelope: null,
  spent: "0.00",
  gap: null,
  gap_ratio: null,
  pace: null,
  status: "none",
  projection: null,
  drift: null,
  projected_gap_ratio: null,
  drifting: false,
  months_over: 0,
  months_on: 0,
  months_under: 0,
  target_from_children: false,
  ...changes,
});

export const runningReview = (changes: Partial<ReviewOut> = {}): ReviewOut => ({
  plan: current(),
  elapsed: "0.5119",
  finished: false,
  band: "0.05",
  rows: [
    reviewRow({
      name: "Food",
      monthly_target: "400.00",
      envelope: "1200.00",
      spent: "700.00",
      gap: "-500.00",
      gap_ratio: "-0.4167",
      pace: "614.28",

      status: "over",
      projection: "1367.45",
      drift: "167.45",
      projected_gap_ratio: "0.1395",
      drifting: true,
      months_over: 1,
      target_from_children: true,
    }),
    reviewRow({
      name: "Restaurants",
      category_id: "c-restaurants",
      parent_id: "c-food",
      level: 1,
      monthly_target: "100.00",
      envelope: "300.00",
      spent: "250.00",
      gap: "-50.00",
      gap_ratio: "-0.1667",
      pace: "153.57",

      status: "over",
      projection: "488.38",
      drift: "188.38",
      projected_gap_ratio: "0.6279",
      drifting: true,
      months_over: 1,
    }),
    reviewRow({
      name: "Housing",
      monthly_target: "850.00",
      envelope: "2550.00",
      spent: "1275.00",
      gap: "-1275.00",
      gap_ratio: "-0.5000",
      pace: "1305.35",

      status: "on",
      projection: "2490.72",
      drift: "-59.28",
      projected_gap_ratio: "-0.0232",
      months_on: 1,
    }),
    reviewRow({ name: "Leisure", spent: "42.00" }),
  ],
  total: reviewRow({
    name: "Total",
    category_id: null,
    monthly_target: "1250.00",
    envelope: "3750.00",
    spent: "2057.00",
    gap: "-1693.00",
    gap_ratio: "-0.4515",
    pace: "1919.63",

    status: "over",
    projection: "4018.36",
    drift: "268.36",
    projected_gap_ratio: "0.0716",
    drifting: true,
  }),
  uncategorised: "40.00",
  provisional: true,
  income: "2400.00",
  savings: "343.00",
  savings_rate: "0.1429",
  planned_savings: "3450.00",
  drifting: ["c-restaurants", "c-food"],
  ...changes,
});

export const cumulativeChart = (envelope = "3750.00"): CumulativeOut => ({
  envelope,
  points: monthsBetween(start, shiftMonth(start, 2)).flatMap((m, i) =>
    [1, 15].map((day) => ({
      day: `${m}-${String(day).padStart(2, "0")}`,
      spent: i === 0 ? String(day * 50) + ".00" : null,
      envelope: String(i * 1250 + day * 40) + ".00",
    })),
  ),
});

export const comparison = (a: PlanOut): ComparisonOut => ({
  a,
  b: current(),
  rows: [
    {
      category_id: "c-food",
      name: "Food",
      parent_id: null,
      level: 0,
      target_a: "400.00",
      target_b: "400.00",
      average_a: "358.00",
      average_b: "455.00",
      change: "97.00",
      change_ratio: "0.2709",
    },
    {
      category_id: null,
      name: "Total",
      parent_id: null,
      level: 0,
      target_a: "1250.00",
      target_b: "1250.00",
      average_a: "1208.00",
      average_b: "1340.00",
      change: "132.00",
      change_ratio: "0.1093",
    },
  ],
});

export const previous = (changes: Partial<PlanOut> = {}): PlanOut =>
  current({
    id: "p-previous",
    period: periodText(periodContaining("quarter", shiftMonth(start, -3))),
    start: shiftMonth(start, -3),
    end: shiftMonth(start, -1),
    editable: false,
    ...changes,
  });
