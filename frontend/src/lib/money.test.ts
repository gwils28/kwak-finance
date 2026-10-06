import { afterEach, expect, test } from "vitest";
import { setCurrentLanguage } from "./locale";
import {
  amountInput,
  formatEur,
  formatEurSigned,
  formatEurWhole,
  formatPercent,
  parseEurInput,
} from "./money";

// Intl separates French groups and the euro sign with (narrow) no-break spaces.
const plain = (text: string) => text.replace(/[  ]/g, " ");

afterEach(() => setCurrentLanguage("en"));

test.each([
  ["1234.56", "€1,234.56", "1 234,56 €"],
  ["-20.00", "-€20.00", "-20,00 €"],
  ["0.10", "€0.10", "0,10 €"],
  ["123456789012.34", "€123,456,789,012.34", "123 456 789 012,34 €"],
])("formatEur(%s) follows the language", (amount, en, fr) => {
  expect(formatEur(amount)).toBe(en);
  setCurrentLanguage("fr");
  expect(plain(formatEur(amount))).toBe(fr);
});

test("whole, signed and percent formats follow the language", () => {
  expect([formatEurWhole("1621.04"), formatEurSigned("12"), formatPercent("0.3564")]).toEqual([
    "€1,621",
    "+€12",
    "36%",
  ]);
  setCurrentLanguage("fr");
  expect(
    [formatEurWhole("1621.04"), formatEurSigned("12"), formatPercent("0.3564")].map(plain),
  ).toEqual(["1 621 €", "+12 €", "36 %"]);
});

test("an amount fills an input with the language's decimal separator", () => {
  expect(amountInput("12.50")).toBe("12.50");
  setCurrentLanguage("fr");
  expect(amountInput("12.50")).toBe("12,50");
});

test.each([
  ["1 500,5", "1500.50"],
  ["1500.50", "1500.50"],
  ["-20", "-20.00"],
  ["+3,1", "3.10"],
  ["0", "0.00"],
  ["1 234,56 €", "1234.56"],
  ["€12.50", "12.50"],
])("parseEurInput(%s)", (text, expected) => {
  expect(parseEurInput(text)).toBe(expected);
});

test.each(["", "12,345", "1,2,3", "abc", "1.234,56", "--1"])("parseEurInput rejects %s", (text) => {
  expect(parseEurInput(text)).toBeNull();
});
