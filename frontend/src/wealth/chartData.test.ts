import { expect, test } from "vitest";
import type { WealthMatrixLineOut, WealthMatrixOut } from "../api/generated";
import { allocation, bridge, fittedAxis, history, netWorth, shownInFilter } from "./chartData";

const ME = "me";

const line = (
  id: string,
  amounts: (string | null)[],
  extra: Partial<WealthMatrixLineOut> = {},
): WealthMatrixLineOut => ({
  id,
  name: id,
  owner_id: ME,
  owner_name: "Wilson",
  visibility: "shared",
  closed_from: null,
  cells: amounts.map((a) => (a === null ? null : { amount: a, carried: false })),
  share: null,
  ...extra,
});

const matrix: WealthMatrixOut = {
  months: ["2026-01", "2026-02"],
  categories: [
    {
      id: "c-savings",
      name: "Savings accounts",
      kind: "asset",
      colour: "savings",
      subtotals: ["1000.00", "1500.00"],
      share: "0.2500",
      lines: [
        line("Livret A", ["1000.00", "1000.00"]),
        line("LDDS", [null, "500.00"], { owner_id: "partner", owner_name: "Alex" }),
      ],
    },
    {
      id: "c-gold",
      name: "Gold",
      kind: "asset",
      colour: "gold",
      subtotals: ["0.00", "0.00"],
      share: "0.0000",
      lines: [],
    },
    {
      id: "c-stocks",
      name: "Stocks",
      kind: "asset",
      colour: "stocks",
      subtotals: ["5000.00", "4500.00"],
      share: "0.7500",
      lines: [
        line("PEA", ["2000.00", "1500.00"]),
        line("CTO", ["3000.00", "3000.00"], { visibility: "joint" }),
      ],
    },
    {
      id: "c-debts",
      name: "Debts",
      kind: "debt",
      colour: "debts",
      subtotals: ["2000.00", "1000.00"],
      share: null,
      lines: [line("Prêt", ["2000.00", "1000.00"])],
    },
  ],
  gross: ["6000.00", "6000.00"],
  debts: ["2000.00", "1000.00"],
  net: ["4000.00", "5000.00"],
  change: [null, "1000.00"],
  change_ratio: [null, "0.2500"],
};

test("the allocation is the last month's assets, by category then line, empty ones left out", () => {
  const a = allocation(matrix);
  expect(a.total).toBe(6000);
  expect(a.categories.map((c) => [c.name, c.value, c.share])).toEqual([
    ["Savings accounts", 1500, 0.25],
    ["Stocks", 4500, 0.75],
  ]);
  // Lines from the largest, each with its share of gross assets.
  expect(a.categories[1]?.lines.map((l) => [l.name, l.value, l.share])).toEqual([
    ["CTO", 3000, 0.5],
    ["PEA", 1500, 0.25],
  ]);
});

test("the allocation can be read for any month shown", () => {
  const january = allocation(matrix, 0);
  expect(january.total).toBe(6000);
  expect(january.categories.map((c) => [c.name, c.value])).toEqual([
    ["Savings accounts", 1000],
    ["Stocks", 5000],
  ]);
  // LDDS had no value yet in January.
  expect(january.categories[0]?.lines.map((l) => l.name)).toEqual(["Livret A"]);
});

test("history stacks the assets above zero and the debts below, with net worth", () => {
  expect(history(matrix)).toEqual([
    { month: "2026-01", "c-savings": 1000, "c-stocks": 5000, "c-debts": -2000, net: 4000 },
    { month: "2026-02", "c-savings": 1500, "c-stocks": 4500, "c-debts": -1000, net: 5000 },
  ]);
});

test("the bridge goes from the first net worth to the last, one step per category that moved", () => {
  expect(bridge(matrix)).toEqual([
    { key: "start", kind: "start", from: 0, to: 4000, delta: 4000 },
    { key: "c-savings", kind: "up", from: 4000, to: 4500, delta: 500 },
    { key: "c-stocks", kind: "down", from: 4500, to: 4000, delta: -500 },
    // Less owed: net worth goes up.
    { key: "c-debts", kind: "up", from: 4000, to: 5000, delta: 1000 },
    { key: "end", kind: "end", from: 0, to: 5000, delta: 5000 },
  ]);
  expect(bridge({ ...matrix, months: ["2026-02"] })).toBeNull();
});

test("net worth can leave categories out, an asset taken off, a debt never counted twice", () => {
  expect(netWorth(matrix)).toEqual([
    { month: "2026-01", net: 4000 },
    { month: "2026-02", net: 5000 },
  ]);
  expect(netWorth(matrix, new Set(["c-stocks"]))).toEqual([
    { month: "2026-01", net: -1000 },
    { month: "2026-02", net: 500 },
  ]);
});

test("the net worth axis fits the values with round steps, never forced to zero", () => {
  expect(fittedAxis([8000, 7750, 8400])).toEqual({
    domain: [7600, 8600],
    ticks: [7600, 7800, 8000, 8200, 8400, 8600],
  });
  // A flat line still gets an axis around it.
  const flat = fittedAxis([5000, 5000]);
  expect(flat.domain[0]).toBeLessThan(5000);
  expect(flat.domain[1]).toBeGreaterThan(5000);
  // Negative values too.
  const low = fittedAxis([-1000, 500]);
  expect(low.domain[0]).toBeLessThanOrEqual(-1000);
  expect(low.domain[1]).toBeGreaterThanOrEqual(500);
  expect(fittedAxis([])).toEqual({ domain: [0, 1], ticks: [0, 1] });
});

test("the filter hides the categories holding nothing over the months shown, unless left out", () => {
  const all = [
    { id: "c-savings" },
    { id: "c-gold" },
    { id: "c-stocks" },
    { id: "c-debts" },
    { id: "c-crypto" },
  ];
  // Gold holds nothing; crypto is not in the matrix because it is left out.
  expect(shownInFilter(all, matrix, ["c-crypto"]).map((c) => c.id)).toEqual([
    "c-savings",
    "c-stocks",
    "c-debts",
    "c-crypto",
  ]);
  // Not in the matrix and not left out (a category added since): kept.
  expect(shownInFilter(all, matrix, []).map((c) => c.id)).toContain("c-crypto");
  // Left out while empty: still shown, so it can be ticked again.
  expect(shownInFilter(all, matrix, ["c-gold"]).map((c) => c.id)).toContain("c-gold");
  // No matrix yet: every category.
  expect(shownInFilter(all, undefined, [])).toHaveLength(5);
});
