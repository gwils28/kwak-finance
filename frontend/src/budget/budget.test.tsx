import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { current, currentLabel, matrix } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function api(extra: Record<string, (body: unknown, url: URL) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/budget/matrix": () => Response.json(matrix),
    "GET /api/budget/plans": () => Response.json([current()]),
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
  expect(header).toEqual(["Category", `Monthly target · ${currentLabel}`, "Feb 2026", "Mar 2026"]);

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
