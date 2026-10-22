import { expect, test } from "vitest";
import { type Draft, defaultDay, draftOf, firstMissing, lineBody, negate } from "./draft";

const groceries = "c-groceries";
const home = "c-home";
const salaries = "c-salaries";
const refunds = "c-refunds";
const NONE = new Set<string>();
const INCOME = new Set([salaries, refunds]);

const draft = (changes: Partial<Draft> = {}): Draft => ({
  day: "2026-10-14",
  label: "Bakery",
  amount: "12,50",
  category: groceries,
  split: null,
  ...changes,
});

test("an amount typed as spent is stored negative, a savings withdrawal positive", () => {
  expect(negate("12.50")).toBe("-12.50");
  expect(negate("-50.00")).toBe("50.00");
  expect(lineBody(draft(), NONE)).toEqual({
    day: "2026-10-14",
    label: "Bakery",
    amount: "-12.50",
    category_id: groceries,
    fixed_expense_id: null,
  });
  expect(lineBody(draft({ amount: "-50" }), NONE)?.amount).toBe("50.00");
});

test("an incomplete or zero line has no body, and says what is missing first", () => {
  expect(lineBody(draft({ label: "  " }), NONE)).toBeNull();
  expect(lineBody(draft({ amount: "0" }), NONE)).toBeNull();
  expect(lineBody(draft({ amount: "12.505" }), NONE)).toBeNull();
  expect(firstMissing(draft({ day: "", category: "" }))).toBe("day");
  expect(firstMissing(draft({ amount: "abc", category: "" }))).toBe("amount");
  expect(firstMissing(draft({ category: "" }))).toBe("category");
  expect(firstMissing(draft())).toBeNull();
});

test("a split sends every part but the last, signed, and the rest's category", () => {
  const split = { parts: [{ category: groceries, amount: "30" }], rest: home };
  expect(lineBody(draft({ amount: "87,40", category: "", split }), NONE)).toEqual({
    day: "2026-10-14",
    label: "Bakery",
    amount: "-87.40",
    split: { parts: [{ category_id: groceries, amount: "-30.00" }], rest_category_id: home },
    fixed_expense_id: null,
  });
  expect(firstMissing(draft({ category: "", split: { ...split, rest: "" } }))).toBe("category");
});

test("a saved line reads back as typed, its split's last part as the rest", () => {
  const line = {
    id: "l1",
    day: "2026-10-14",
    label: "Supermarket",
    amount: "-87.40",
    category_id: null,
    parts: [
      { category_id: groceries, amount: "-30.00" },
      { category_id: home, amount: "-57.40" },
    ],
    fixed_expense_id: null,
    entered_by: "Wilson",
    entered_at: "2026-10-15T08:00:00Z",
  };
  expect(draftOf(line, NONE)).toEqual({
    day: "2026-10-14",
    label: "Supermarket",
    amount: "87.40",
    category: "",
    split: { parts: [{ category: groceries, amount: "30" }], rest: home },
  });
});

test("an income line is typed and stored positive, a split of incomes too", () => {
  expect(lineBody(draft({ amount: "2500", category: salaries }), INCOME)?.amount).toBe("2500.00");
  const split = { parts: [{ category: salaries, amount: "2000" }], rest: refunds };
  expect(lineBody(draft({ amount: "2100", category: "", split }), INCOME)).toMatchObject({
    amount: "2100.00",
    split: { parts: [{ category_id: salaries, amount: "2000.00" }], rest_category_id: refunds },
  });
  const line = {
    day: "2026-10-01",
    label: "Pay",
    amount: "2500.00",
    category_id: salaries,
    parts: [],
  };
  expect(draftOf(line, INCOME).amount).toBe("2500");
});

test("a new row's date: the session's, else today, a past month's last day, a later one's first", () => {
  expect(defaultDay("2026-10", "2026-10-22", "2026-10-03")).toBe("2026-10-03");
  expect(defaultDay("2026-10", "2026-10-22", "2026-09-30")).toBe("2026-10-22");
  expect(defaultDay("2026-10", "2026-10-22", null)).toBe("2026-10-22");
  expect(defaultDay("2026-02", "2026-10-22", null)).toBe("2026-02-28");
  expect(defaultDay("2026-12", "2026-10-22", null)).toBe("2026-12-01");
});
