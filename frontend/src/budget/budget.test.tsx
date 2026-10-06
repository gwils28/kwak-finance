import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { thisMonth } from "./BudgetPage";

afterEach(() => vi.unstubAllGlobals());

const cell = (
  month: string,
  spent: string,
  target: string | null,
  status: string,
  gap: string | null = null,
  ratio: string | null = null,
) => ({
  month,
  spent,
  target,
  gap,
  gap_ratio: ratio,
  status,
});
const months = ["2026-02", "2026-03"];
const matrix = {
  months,
  band: "0.05",
  rows: [
    {
      category_id: "c-food",
      name: "Food",
      parent_id: null,
      level: 0,
      target: "360.00",
      target_from_children: true,
      cells: [
        cell("2026-02", "300.00", "360.00", "under", "-60.00", "-0.1667"),
        cell("2026-03", "362.00", "360.00", "on", "2.00", "0.0056"),
      ],
    },
    {
      category_id: "c-bakery",
      name: "Bakery and coffee",
      parent_id: "c-food",
      level: 1,
      target: "60.00",
      cells: [
        cell("2026-02", "40.00", "60.00", "under", "-20.00", "-0.3333"),
        cell("2026-03", "72.00", "60.00", "over", "12.00", "0.2000"),
      ],
    },
    {
      category_id: "c-groceries",
      name: "Groceries",
      parent_id: "c-food",
      level: 1,
      target: null,
      cells: [cell("2026-02", "260.00", null, "none"), cell("2026-03", "290.00", null, "none")],
    },
    {
      category_id: "c-edu",
      name: "Education",
      parent_id: null,
      level: 0,
      target: null,
      cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "0.00", null, "none")],
    },
    {
      category_id: "c-books",
      name: "Books",
      parent_id: "c-edu",
      level: 1,
      target: null,
      cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "0.00", null, "none")],
    },
  ],
  uncategorised: {
    category_id: null,
    name: "To categorise",
    parent_id: null,
    level: 0,
    target: null,
    cells: [cell("2026-02", "0.00", null, "none"), cell("2026-03", "25.50", null, "none")],
  },
  total: {
    category_id: null,
    name: "Total",
    parent_id: null,
    level: 0,
    target: "360.00",
    cells: [
      cell("2026-02", "300.00", "360.00", "under", "-60.00", "-0.1667"),
      cell("2026-03", "387.50", "360.00", "over", "27.50", "0.0764"),
    ],
  },
};

function api(extra: Record<string, (body: unknown, url: URL) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/budget/matrix": () => Response.json(matrix),
    ...extra,
  });
}

function matrixQueries(): URLSearchParams[] {
  return vi
    .mocked(fetch)
    .mock.calls.map(([r]) => new URL((r as Request).url))
    .filter((u) => u.pathname === "/api/budget/matrix")
    .map((u) => u.searchParams);
}

test("the matrix shows categories by month with the gap and a colour", async () => {
  api();
  render(<TestApp path="/budget" />);

  const table = await screen.findByRole("table", { name: "Budget by category and month" });
  const header = within(table)
    .getAllByRole("columnheader")
    .map((h) => h.textContent);
  expect(header).toEqual(["Category", "Monthly target", "Feb 2026", "Mar 2026"]);

  const bakery = within(table).getByRole("row", { name: /Bakery and coffee/ });
  const march = within(bakery).getAllByRole("cell").at(-1) as HTMLElement;
  expect(march).toHaveAttribute("data-status", "over");
  expect(march).toHaveTextContent("€72");
  expect(march).toHaveTextContent("+€12 · +20%");

  const groceries = within(table).getByRole("row", { name: /Groceries/ });
  expect(within(groceries).getAllByRole("cell").at(-1)).toHaveAttribute("data-status", "none");
  expect(within(table).getByRole("row", { name: /To categorise/ })).toHaveTextContent("€26");
  expect(within(table).getByRole("row", { name: /Total/ })).toHaveTextContent("€388");
  expect(screen.getByText(/more than 5% below/)).toBeInTheDocument();
});

test("a target is edited in place and applies from this month on", async () => {
  const calls = api({
    "PUT /api/budget/targets/c-groceries": (body) =>
      Response.json({ category_id: "c-groceries", ...(body as object) }),
  });
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  const input = await screen.findByLabelText("Monthly target for Groceries");
  await user.type(input, "300{Enter}");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/budget/targets/c-groceries")?.body).toEqual({
      amount: "300.00",
      from_month: thisMonth(),
    }),
  );
});

test("emptying a target removes it from this month on", async () => {
  const calls = api({
    "PUT /api/budget/targets/c-bakery": (body) =>
      Response.json({ category_id: "c-bakery", ...(body as object) }),
  });
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  const input = await screen.findByLabelText("Monthly target for Bakery and coffee");
  expect(input).toHaveValue("60");
  await user.clear(input);
  await user.tab();

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/budget/targets/c-bakery")?.body).toEqual({
      amount: null,
      from_month: thisMonth(),
    }),
  );
});

test("a bad target is refused before sending", async () => {
  const calls = api();
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  await user.type(await screen.findByLabelText("Monthly target for Groceries"), "-5{Enter}");

  expect(await screen.findByRole("alert")).toHaveTextContent("Groceries: enter a positive amount");
  expect(calls.some((c) => c.route.startsWith("PUT"))).toBe(false);
});

test("a cell opens the month's transactions of its category", async () => {
  api();
  render(<TestApp path="/budget" />);

  const link = await screen.findByRole("link", { name: /^Bakery and coffee, Mar 2026: €72$/ });
  expect(link).toHaveAttribute(
    "href",
    "/transactions?category=c-bakery&from=2026-03-01&to=2026-03-31",
  );
  const todo = screen.getByRole("link", { name: /^To categorise, Feb 2026: €0$/ });
  expect(todo).toHaveAttribute("href", "/transactions?category=none&from=2026-02-01&to=2026-02-28");
});

test("scope and band are sent to the API", async () => {
  api();
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  await user.selectOptions(await screen.findByLabelText("Accounts"), "mine");
  await user.selectOptions(screen.getByLabelText("Margin"), "0.10");

  await vi.waitFor(() => {
    const last = matrixQueries().at(-1);
    expect(last?.get("scope")).toBe("mine");
    expect(last?.get("band")).toBe("0.10");
  });
});

test("the header links to the budget", async () => {
  api();
  render(<TestApp path="/" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Budget" }));
  expect(await screen.findByRole("heading", { name: "Budget" })).toBeInTheDocument();
});

test("a parent's target that only sums its subcategories is shown as a hint, not a value", async () => {
  api();
  render(<TestApp path="/budget" />);

  const food = await screen.findByLabelText("Monthly target for Food");
  expect(food).toHaveValue("");
  expect(food.getAttribute("placeholder")).toMatch(/^€360 \(sum\)$/);
});

test("categories with no spending and no target are hidden until asked for", async () => {
  api();
  render(<TestApp path="/budget" />);

  const table = await screen.findByRole("table", { name: "Budget by category and month" });
  expect(within(table).queryByRole("row", { name: /Education/ })).toBeNull();
  expect(within(table).queryByRole("row", { name: /Books/ })).toBeNull();

  await userEvent
    .setup()
    .click(screen.getByLabelText("Show categories with no spending or target"));

  expect(within(table).getByRole("row", { name: /Education/ })).toBeInTheDocument();
  expect(within(table).getByRole("row", { name: /Books/ })).toBeInTheDocument();
});
