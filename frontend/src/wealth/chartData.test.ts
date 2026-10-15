import { expect, test } from "vitest";
import type { WealthMatrixLineOut, WealthMatrixOut } from "../api/generated";
import { allocation, bridge, history, holdings, JOINT } from "./chartData";

const ME = "me";
const PARTNER = "partner";

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
        line("LDDS", [null, "500.00"], { owner_id: PARTNER, owner_name: "Alex" }),
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

test("holdings split each category by holder: the viewer first, joint last", () => {
  const h = holdings(matrix, ME);
  expect(h.holders.map((x) => x.key)).toEqual([ME, PARTNER, JOINT]);
  expect(h.holders.map((x) => x.name)).toEqual(["Wilson", "Alex", null]);
  const stocks = h.columns.find((c) => c.name === "Stocks");
  expect(stocks?.share).toBe(0.75);
  expect(stocks?.parts).toEqual([
    { holder: ME, value: 1500, share: 1 / 3 },
    { holder: JOINT, value: 3000, share: 2 / 3 },
  ]);
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
