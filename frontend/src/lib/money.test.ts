import { expect, test } from "vitest";
import { formatEur, parseEurInput } from "./money";

test.each([
  ["1234.56", "1 234,56 €"],
  ["-20.00", "-20,00 €"],
  ["0.10", "0,10 €"],
  ["123456789012.34", "123 456 789 012,34 €"],
])("formatEur(%s)", (amount, expected) => {
  expect(formatEur(amount).replace(/[  ]/g, " ")).toBe(expected);
});

test.each([
  ["1 500,5", "1500.50"],
  ["1500.50", "1500.50"],
  ["-20", "-20.00"],
  ["+3,1", "3.10"],
  ["0", "0.00"],
  ["1 234,56 €", "1234.56"],
])("parseEurInput(%s)", (text, expected) => {
  expect(parseEurInput(text)).toBe(expected);
});

test.each(["", "12,345", "1,2,3", "abc", "1.234,56", "--1"])("parseEurInput rejects %s", (text) => {
  expect(parseEurInput(text)).toBeNull();
});
