import { expect, test } from "vitest";
import { type FlowEntry, flowGraph } from "./flowGraph";

const entry = (key: string, side: "in" | "out", amount: number): FlowEntry => ({
  key,
  label: key,
  side,
  role: side === "in" ? "income" : "spent",
  amount,
  over: false,
});

test("several sources flow into a hub, then out", () => {
  const g = flowGraph(
    [entry("Salaries", "in", 2000), entry("Aids", "in", 500)],
    [entry("Housing", "out", 2500)],
    "Money in",
  );
  expect(g.nodes.map((n) => n.label)).toEqual(["Salaries", "Aids", "Money in", "Housing"]);
  expect(g.hub).toBe(2);
  expect(g.links.map((l) => [l.source, l.target, l.value])).toEqual([
    [0, 2, 2000],
    [1, 2, 500],
    [2, 3, 2500],
  ]);
});

test("a single source is the hub itself, not a band as wide as the chart", () => {
  const g = flowGraph(
    [entry("Salaries", "in", 2500)],
    [entry("Housing", "out", 1500), entry("Groceries", "out", 1000)],
    "Money in",
  );
  expect(g.nodes.map((n) => n.label)).toEqual(["Salaries", "Housing", "Groceries"]);
  expect(g.hub).toBe(0);
  expect(g.nodes[0]?.role).toBe("income");
  expect(g.links.map((l) => [l.source, l.target, l.value])).toEqual([
    [0, 1, 1500],
    [0, 2, 1000],
  ]);
});

test("a source of 90 % or more leaves the hub alone, without a plain band into it", () => {
  const g = flowGraph(
    [entry("Salaries", "in", 6000), entry("Aids", "in", 25)],
    [entry("Housing", "out", 6025)],
    "Money in",
  );
  expect(g.nodes.map((n) => n.label)).toEqual(["Money in", "Housing"]);
  expect(g.hub).toBe(0);
  expect(g.nodes[0]?.role).toBe("hub");
  expect(g.nodes[0]?.amount).toBe(6025);
  expect(g.links.map((l) => [l.source, l.target, l.value])).toEqual([[0, 1, 6025]]);
});
