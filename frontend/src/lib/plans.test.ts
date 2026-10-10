import { expect, test } from "vitest";
import type { PlanOut } from "../api/generated";
import {
  nextPeriod,
  parsePeriod,
  periodContaining,
  periodStart,
  periodText,
  planTargets,
  suggestedPeriod,
} from "./plans";

const plan = (period: string, start: string, end: string, targets: [string, string][] = []) =>
  ({
    id: period,
    period,
    kind: parsePeriod(period).kind,
    start,
    end,
    targets: targets.map(([category_id, amount]) => ({ category_id, amount })),
    expected_income: null,
    note: null,
    closed_early: false,
    close_reason: null,
    editable: true,
  }) satisfies PlanOut;

test.each(["2027", "2027-S2", "2027-Q3"])("%s reads back as written", (text) => {
  expect(periodText(parsePeriod(text))).toBe(text);
});

test("periods start on their calendar month", () => {
  expect(periodStart(parsePeriod("2027-Q3"))).toBe("2027-07");
  expect(periodStart(parsePeriod("2027-S2"))).toBe("2027-07");
  expect(periodStart(parsePeriod("2027"))).toBe("2027-01");
  expect(periodContaining("quarter", "2026-10")).toEqual({
    kind: "quarter",
    year: 2026,
    number: 4,
  });
});

test("the next period rolls over the year", () => {
  expect(periodText(nextPeriod(parsePeriod("2026-Q4")))).toBe("2027-Q1");
  expect(periodText(nextPeriod(parsePeriod("2026-S1")))).toBe("2026-S2");
  expect(periodText(nextPeriod(parsePeriod("2026")))).toBe("2027");
});

test("a new plan follows the latest one, or covers this month's quarter", () => {
  expect(periodText(suggestedPeriod([], "2026-10"))).toBe("2026-Q4");
  const s2 = plan("2026-S2", "2026-07", "2026-12");
  expect(periodText(suggestedPeriod([s2], "2026-10"))).toBe("2027-S1");
  const old = plan("2025", "2025-01", "2025-12");
  expect(periodText(suggestedPeriod([old], "2026-10"))).toBe("2026");
});

test("a parent without its own target shows its children's sum, counted once in the total", () => {
  const rows = [
    { category_id: "food", parent_id: null, level: 0 },
    { category_id: "bakery", parent_id: "food", level: 1 },
    { category_id: "groceries", parent_id: "food", level: 1 },
    { category_id: "home", parent_id: null, level: 0 },
  ];
  const q4 = plan("2026-Q4", "2026-10", "2026-12", [
    ["bakery", "60.50"],
    ["groceries", "300.00"],
    ["home", "900.00"],
  ]);
  const { byCategory, total } = planTargets(q4, rows);
  expect(byCategory.get("food")).toEqual({ amount: "360.50", fromChildren: true });
  expect(byCategory.get("home")).toEqual({ amount: "900.00", fromChildren: false });
  expect(total).toBe("1260.50");
  expect(planTargets(plan("2027", "2027-01", "2027-12"), rows).total).toBeNull();
});
