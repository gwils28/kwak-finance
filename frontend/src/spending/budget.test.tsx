import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { SpendingMatrixOut, SpendingYearOut } from "../api/generated";
import { thisMonth } from "../lib/months";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { groceries, savingsCategory, spendingCategories } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

const current = thisMonth();
const cell = (
  spent: string,
  target: string | null,
  status: string,
  gap = null as string | null,
) => ({
  month: current,
  spent,
  target,
  gap,
  gap_ratio: gap === null ? null : "0.2000",
  status,
});
const matrix = {
  months: [current],
  rows: [
    {
      category_id: groceries.id,
      name: "Groceries",
      target: "50.00",
      cells: [cell("60.00", "50.00", "over", "10.00")],
    },
  ],
  total: {
    category_id: null,
    name: "Total",
    target: "50.00",
    cells: [cell("60.00", "50.00", "over")],
  },
  savings: [
    {
      category_id: savingsCategory.id,
      name: "Savings",
      target: null,
      cells: [cell("200.00", null, "none")],
    },
  ],
  savings_total: {
    category_id: null,
    name: "Total",
    target: null,
    cells: [cell("200.00", null, "none")],
  },
  figures: [
    { income: "3000.00", spent: "60.00", saved: "200.00", rest: "2740.00", savings_rate: "0.98" },
  ],
} as SpendingMatrixOut;

const year = {
  year: 2026,
  months: ["2026-01", "2026-02"],
  expenses: [
    {
      category_id: groceries.id,
      name: "Groceries",
      target_to_date: "100.00",
      target_full: "600.00",
      spent_to_date: "90.00",
      gap: "-10.00",
      gap_ratio: "-0.1000",
      status: "under",
      above: 0,
      on: 1,
      below: 1,
    },
  ],
  savings: [],
  totals: {
    income: "6000.00",
    spent: "90.00",
    saved: "0.00",
    rest: "5910.00",
    savings_rate: "0.985",
  },
} as SpendingYearOut;

type Handler = (body: unknown, url: URL) => Response;

function api(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/spending/categories": () => Response.json(spendingCategories),
    "GET /api/spending/matrix": () => Response.json(matrix),
    "GET /api/spending/year": () => Response.json(year),
    "GET /api/spending/targets": () =>
      Response.json([{ category_id: groceries.id, from_month: "2026-01", amount: "50.00" }]),
    ...extra,
  });
}

test("the matrix shows each category's month against its target, coloured and said in words", async () => {
  api();
  render(<TestApp path="/budget" />);

  const table = await screen.findByRole("table", { name: "Spending by category and month" });
  const row = within(table).getByRole("row", { name: /^Groceries/ });
  expect(within(row).getByRole("button", { name: "Target of Groceries" })).toHaveTextContent("€50");
  const link = within(row).getByRole("link", { name: /Groceries, .*: open its lines/ });
  expect(link).toHaveTextContent("€60");
  expect(link).toHaveTextContent("+€10 · +20%");
  expect(link).toHaveAccessibleName(/over target/);
  expect(link).toHaveAttribute("href", `/spending?month=${current}&category=${groceries.id}`);
  expect(within(table).getByRole("row", { name: /^Rest/ })).toHaveTextContent("+€2,740");
});

test("a target is set from a month on", async () => {
  const calls = api({
    [`PUT /api/spending/targets/${groceries.id}/${current}`]: (body) =>
      Response.json({ category_id: groceries.id, from_month: current, ...(body as object) }),
  });
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Target of Groceries" }));
  const form = screen.getByRole("form", { name: "Monthly target of Groceries" });
  const amount = within(form).getByLabelText("Amount per month");
  expect(amount).toHaveValue("50");
  await user.clear(amount);
  await user.type(amount, "65,50");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  await vi.waitFor(() =>
    expect(
      calls.find((c) => c.route === `PUT /api/spending/targets/${groceries.id}/${current}`)?.body,
    ).toEqual({ amount: "65.50" }),
  );
  expect(await screen.findByText("Target saved.")).toBeVisible();
});

test("a target set from a past month says which months take it", async () => {
  api();
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Target of Groceries" }));
  fireEvent.change(screen.getByLabelText("From"), { target: { value: "2025-03" } });
  expect(screen.getByText(/The months from Mar 2025 on take this amount/)).toBeVisible();
  expect(screen.getByText(/From Jan 2026: €50/)).toBeVisible();
});

test("the year adds up the targets to date and counts the months", async () => {
  api();
  render(<TestApp path="/budget?view=year&year=2026" />);

  const table = await screen.findByRole("table", { name: "Spending of 2026 by category" });
  const row = within(table).getByRole("row", { name: /^Groceries/ });
  expect(row).toHaveTextContent("€100");
  expect(row).toHaveTextContent("€90");
  expect(row).toHaveTextContent("-€10 · -10%");
  expect(row).toHaveTextContent("under target");
  expect(row).toHaveTextContent("0 · 1 · 1");
  expect(row).toHaveTextContent("€600");
  expect(screen.getByRole("region", { name: "The year so far" })).toHaveTextContent("€5,910");
  expect(screen.getByRole("link", { name: "The year" })).toHaveAttribute("aria-current", "page");
});

test("the budget reads in French", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/spending/categories": () => Response.json(spendingCategories),
    "GET /api/spending/matrix": () => Response.json(matrix),
  });
  render(<TestApp path="/budget" language="fr" />);

  const table = await screen.findByRole("table", { name: "Dépenses par catégorie et par mois" });
  expect(within(table).getByRole("button", { name: "Cible de Groceries" })).toHaveTextContent(
    /50\s€/,
  );
  expect(within(table).getByRole("link", { name: /au-dessus de la cible/ })).toBeInTheDocument();
});

test("a target is ended from a month, and a change can be removed", async () => {
  const calls = api({
    [`PUT /api/spending/targets/${groceries.id}/${current}`]: (body) =>
      Response.json({ category_id: groceries.id, from_month: current, ...(body as object) }),
    [`DELETE /api/spending/targets/${groceries.id}/2026-01`]: () =>
      new Response(null, { status: 204 }),
  });
  render(<TestApp path="/budget" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Target of Groceries" }));
  await user.click(screen.getByRole("button", { name: "No target from this month" }));
  await vi.waitFor(() =>
    expect(
      calls.find((c) => c.route === `PUT /api/spending/targets/${groceries.id}/${current}`)?.body,
    ).toEqual({ amount: null }),
  );

  await user.click(await screen.findByRole("button", { name: "Target of Groceries" }));
  await user.click(await screen.findByRole("button", { name: "Remove the change of Jan 2026" }));
  expect(await screen.findByText("Change removed.")).toBeVisible();
  expect(screen.queryByRole("form", { name: "Monthly target of Groceries" })).toBeNull();
});

test("a past year is shown whole, without the running month's note", async () => {
  api();
  render(<TestApp path="/budget?view=year&year=2015" />);

  await screen.findByRole("table", { name: "Spending of 2015 by category" });
  expect(screen.getByLabelText("Year")).toHaveValue("2015");
  expect(screen.queryByText(/a running month leans under/)).toBeNull();
});
