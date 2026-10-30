import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { FixedOut } from "../api/generated";
import { en } from "../i18n/en";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { groceries, home, housing, spendingCategories, spendingHandlers } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

type Handler = (body: unknown, url: URL) => Response;

const rentItem: FixedOut = {
  id: "f-rent",
  label: "Rent",
  category_id: housing.id,
  amount: "-950.00",
  frequency: "monthly",
  day: 5,
  first_month: "2026-01",
  last_month: null,
  paused: false,
};

function api(extra: Record<string, Handler> = {}, user = owner) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(user),
    ...spendingHandlers(),
    "GET /api/spending/fixed": () => Response.json([rentItem]),
    ...extra,
  });
}

test("the fixed expenses are listed with their frequency", async () => {
  api();
  render(<TestApp path="/spending/fixed" />);

  const table = await screen.findByRole("table", { name: "Fixed expenses" });
  const row = within(table).getAllByRole("row")[1] as HTMLElement;
  expect(row).toHaveTextContent("Rent");
  expect(row).toHaveTextContent("Housing");
  expect(row).toHaveTextContent("€950.00");
  expect(row).toHaveTextContent("Every month on the 5th · from Jan 2026");
  expect(row).toHaveTextContent("Active");
});

test("English days of the month take their ordinal", () => {
  expect(en.spending.fixedPage.dayOf(1)).toBe("on the 1st");
  expect(en.spending.fixedPage.dayOf(11)).toBe("on the 11th");
  expect(en.spending.fixedPage.dayOf(22)).toBe("on the 22nd");
  expect(en.spending.fixedPage.dayOf(23)).toBe("on the 23rd");
  expect(en.spending.fixedPage.dayOf(31)).toBe("on the 31st");
});

test("a fixed expense is added as an outflow", async () => {
  const calls = api({
    "POST /api/spending/fixed": (body) =>
      Response.json({ ...rentItem, id: "f2", ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/spending/fixed" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a fixed expense" }));
  await user.type(screen.getByLabelText("Label"), "Streaming");
  await user.selectOptions(screen.getByLabelText("Category"), home.id);
  await user.type(screen.getByLabelText("Amount"), "13,49");
  await user.selectOptions(screen.getByLabelText("Frequency"), "yearly");
  await user.clear(screen.getByLabelText("Day of the month"));
  await user.type(screen.getByLabelText("Day of the month"), "31");
  await user.click(screen.getByRole("button", { name: "Save" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/fixed")?.body).toMatchObject({
      label: "Streaming",
      category_id: home.id,
      amount: "-13.49",
      frequency: "yearly",
      day: 31,
      last_month: null,
      paused: false,
    }),
  );
  expect(await screen.findByText("Fixed expense saved.")).toBeVisible();
});

test("the fixed expense's category list has no empty income group", async () => {
  api();
  render(<TestApp path="/spending/fixed" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a fixed expense" }));
  const groups = screen.getByLabelText("Category").querySelectorAll("optgroup");
  expect([...groups].map((g) => g.label)).toEqual(["Expenses", "Savings"]);
});

test("deleting a fixed expense asks first", async () => {
  const calls = api({
    "DELETE /api/spending/fixed/f-rent": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/spending/fixed" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete Rent" }));
  expect(screen.getByText("Delete it? The lines already confirmed stay.")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Delete" }));
  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "DELETE /api/spending/fixed/f-rent")).toBe(true),
  );
});

test("the categories are grouped by kind, renamed in place, one-off for expenses only", async () => {
  const calls = api({
    "PATCH /api/spending/categories/c-groceries": (body) =>
      Response.json({ ...groceries, ...(body as object) }),
  });
  render(<TestApp path="/spending/categories" />);

  const expenses = await screen.findByRole("region", { name: "Expense categories" });
  expect(within(expenses).getAllByRole("listitem")).toHaveLength(3);
  const savings = screen.getByRole("region", { name: "Savings categories" });
  expect(within(savings).queryByLabelText("One-off")).toBeNull();
  expect(within(expenses).getAllByLabelText("One-off")[0]).toBeChecked();

  const user = userEvent.setup();
  const name = screen.getByLabelText("Rename Groceries");
  await user.clear(name);
  await user.type(name, "Food{Enter}");
  await vi.waitFor(() =>
    expect(
      calls.find((c) => c.route === "PATCH /api/spending/categories/c-groceries")?.body,
    ).toEqual({ name: "Food" }),
  );
});

test("a category holding lines is deleted by moving them to another of its kind", async () => {
  const calls = api({
    "DELETE /api/spending/categories/c-home": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/spending/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete Home" }));
  const target = screen.getByLabelText("Move its lines, fixed expenses and targets to");
  expect(within(target).queryByRole("option", { name: "Savings" })).toBeNull();
  await user.selectOptions(target, groceries.id);
  await user.click(screen.getByRole("button", { name: "Delete" }));

  await vi.waitFor(() => {
    const call = vi
      .mocked(fetch)
      .mock.calls.map(([request]) => new URL((request as Request).url))
      .find((url) => url.pathname === "/api/spending/categories/c-home");
    expect(call?.searchParams.get("move_to")).toBe(groceries.id);
  });
  expect(calls.some((c) => c.route === "DELETE /api/spending/categories/c-home")).toBe(true);
});

test("only the owner restores the default categories", async () => {
  api({ "POST /api/spending/categories/restore": () => Response.json({ added: 2 }) });
  const { unmount } = render(<TestApp path="/spending/categories" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Restore defaults" }));
  expect(await screen.findByText("2 categories added back.")).toBeVisible();
  unmount();
  vi.unstubAllGlobals();

  api({}, { ...owner, role: "member" });
  render(<TestApp path="/spending/categories" />);
  await screen.findByRole("region", { name: "Expense categories" });
  const income = screen.getByRole("region", { name: "Income categories" });
  expect(within(income).getByLabelText("Rename Salaries")).toHaveValue("Salaries");
  expect(screen.queryByRole("button", { name: "Restore defaults" })).toBeNull();
  expect(spendingCategories).toHaveLength(5);
});
