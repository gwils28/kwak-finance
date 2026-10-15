import { expect, test } from "vitest";
import type { WealthMatrixLineOut, WealthMatrixOut } from "../api/generated";
import { allocation, bridge, history, mosaic, squarify } from "./chartData";

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

const area = (r: { w: number; h: number }) => r.w * r.h;

test("squarify tiles the rectangle, each area proportional to its value", () => {
  const values = [6, 6, 4, 3, 2, 2, 1];
  const tiles = squarify(values, { x: 0, y: 0, w: 600, h: 400 });
  expect(tiles).toHaveLength(7);
  const total = 600 * 400;
  tiles.forEach((tile, i) => {
    expect(area(tile) / total).toBeCloseTo((values[i] ?? 0) / 24, 6);
    expect(tile.x).toBeGreaterThanOrEqual(-1e-9);
    expect(tile.y).toBeGreaterThanOrEqual(-1e-9);
    expect(tile.x + tile.w).toBeLessThanOrEqual(600 + 1e-9);
    expect(tile.y + tile.h).toBeLessThanOrEqual(400 + 1e-9);
  });
  // Squarified: no sliver thinner than a tenth of its length here.
  for (const tile of tiles)
    expect(Math.min(tile.w, tile.h) / Math.max(tile.w, tile.h)).toBeGreaterThan(0.1);
  expect(squarify([], { x: 0, y: 0, w: 10, h: 10 })).toEqual([]);
});

test("the mosaic tiles the categories, largest first, each as large as its value", () => {
  const tiles = mosaic(allocation(matrix), { x: 0, y: 0, w: 600, h: 400 });
  expect(tiles.map((t) => t.category.name)).toEqual(["Stocks", "Savings accounts"]);
  expect(area(tiles[0]?.rect ?? { w: 0, h: 0 }) / (600 * 400)).toBeCloseTo(0.75, 6);
  expect(area(tiles[1]?.rect ?? { w: 0, h: 0 }) / (600 * 400)).toBeCloseTo(0.25, 6);
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
