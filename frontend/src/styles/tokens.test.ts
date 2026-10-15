import { expect, test } from "vitest";
import tokens from "./tokens.css?raw";

/** The colour keys a wealth category can take (`WEALTH_COLOURS` in kwak_core.wealth). */
const WEALTH_KEYS = [
  "savings",
  "current",
  "stocks",
  "crypto",
  "bonds",
  "private-equity",
  "gold",
  "real-estate",
  "equipment",
  "exotic",
  "debts",
];

const block = (opening: string) => {
  const start = tokens.indexOf(opening);
  expect(start, `${opening} not found`).toBeGreaterThanOrEqual(0);
  return tokens.slice(start, tokens.indexOf("\n}", start));
};

const wealthKeys = (css: string) =>
  [...css.matchAll(/--color-wealth-([a-z-]+):/g)].map((m) => m[1]).sort();

test("wealth colours survive the build in both themes", () => {
  // Tailwind drops a plain @theme variable that no utility class uses, and wealth colours are
  // only read through var() from the page: they must sit in a `@theme static` block.
  expect(wealthKeys(block("@theme static {"))).toEqual([...WEALTH_KEYS].sort());
  expect(wealthKeys(block(':root[data-theme="dark"] {'))).toEqual([...WEALTH_KEYS].sort());
});
