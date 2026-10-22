import { expect, test } from "vitest";
import { WEALTH_COLOURS as WEALTH_KEYS } from "../wealth/colours";
import tokens from "./tokens.css?raw";

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

const goalKeys = (css: string) =>
  [...css.matchAll(/--color-goal-([a-z0-9-]+):/g)].map((m) => m[1]).sort();

test("goal colours survive the build in both themes", () => {
  const keys = [
    "foundation",
    "priority",
    "stone",
    "stone-edge",
    "stone-top",
    "tier-1",
    "tier-2",
    "tier-3",
  ];
  expect(goalKeys(block("@theme static {"))).toEqual(keys);
  expect(goalKeys(block(':root[data-theme="dark"] {'))).toEqual(keys);
});

const spendKeys = (css: string) =>
  [...css.matchAll(/--color-spend-([a-z0-9-]+):/g)].map((m) => m[1]).sort();

test("spending category colours survive the build in both themes", () => {
  const keys = ["1", "2", "3", "4", "5", "6", "other"];
  expect(spendKeys(block("@theme static {"))).toEqual(keys);
  // Grey in both themes: the dark one keeps the light one's.
  expect(spendKeys(block(':root[data-theme="dark"] {'))).toEqual(keys.slice(0, 6));
});
