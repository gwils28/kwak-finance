import { expect, test } from "vitest";
import { type Draft, defaultDay, draftOf, firstMissing, lineBody, negate } from "./draft";

const groceries = "c-groceries";
const home = "c-home";

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
  expect(lineBody(draft())).toEqual({
    day: "2026-10-14",
    label: "Bakery",
    amount: "-12.50",
    category_id: groceries,
    fixed_expense_id: null,
  });
  expect(lineBody(draft({ amount: "-50" }))?.amount).toBe("50.00");
});

test("an incomplete or zero line has no body, and says what is missing first", () => {
  expect(lineBody(draft({ label: "  " }))).toBeNull();
  expect(lineBody(draft({ amount: "0" }))).toBeNull();
  expect(lineBody(draft({ amount: "12.505" }))).toBeNull();
  expect(firstMissing(draft({ day: "", category: "" }))).toBe("day");
  expect(firstMissing(draft({ amount: "abc", category: "" }))).toBe("amount");
  expect(firstMissing(draft({ category: "" }))).toBe("category");
  expect(firstMissing(draft())).toBeNull();
});

test("a split sends every part but the last, signed, and the rest's category", () => {
  const split = { parts: [{ category: groceries, amount: "30" }], rest: home };
  expect(lineBody(draft({ amount: "87,40", category: "", split }))).toEqual({
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
  expect(draftOf(line)).toEqual({
    day: "2026-10-14",
    label: "Supermarket",
    amount: "87.40",
    category: "",
    split: { parts: [{ category: groceries, amount: "30" }], rest: home },
  });
});

test("a new row's date: the session's, else today, a past month's last day, a later one's first", () => {
  expect(defaultDay("2026-10", "2026-10-22", "2026-10-03")).toBe("2026-10-03");
  expect(defaultDay("2026-10", "2026-10-22", "2026-09-30")).toBe("2026-10-22");
  expect(defaultDay("2026-10", "2026-10-22", null)).toBe("2026-10-22");
  expect(defaultDay("2026-02", "2026-10-22", null)).toBe("2026-02-28");
  expect(defaultDay("2026-12", "2026-10-22", null)).toBe("2026-12-01");
});
