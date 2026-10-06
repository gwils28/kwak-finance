import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

beforeAll(() => {
  // Recharts measures its container; jsdom has no layout engine.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});
afterEach(() => vi.unstubAllGlobals());

const monthly = Array.from({ length: 12 }, (_, i) => {
  const month = `${i < 2 ? 2025 : 2026}-${String(((i + 3) % 12) + 1).padStart(2, "0")}`;
  const by_category =
    i === 11
      ? [
          { category_id: "c-housing", name: "Housing", spent: "850.00", share: "0.5244" },
          { category_id: "c-food", name: "Food", spent: "406.40", share: "0.2507" },
        ]
      : [];
  return { month, spent: i === 11 ? "1621.04" : "1400.00", income: "2500.00", by_category };
});
const dashboard = {
  month: "2026-03",
  kpis: {
    spent: "1621.04",
    income: "2518.65",
    net: "897.61",
    savings_rate: "0.3564",
    previous_spent: "1400.00",
    average_spent: "1500.00",
    spent_change_vs_previous: "0.1579",
    spent_change_vs_average: "0.0807",
  },
  top_categories: [
    { category_id: "c-housing", name: "Housing", spent: "850.00", share: "0.5244" },
    { category_id: "c-food", name: "Food", spent: "406.40", share: "0.2507" },
  ],
  to_categorise: { count: 10, spent: "364.64" },
  monthly,
  cumulative: Array.from({ length: 31 }, (_, i) => ({
    day: `2026-03-${String(i + 1).padStart(2, "0")}`,
    spent: (i * 50).toFixed(2),
  })),
  budget_target: "1800.00",
};

function api(data: unknown = dashboard) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/dashboard": () => Response.json(data),
  });
}

function dashboardQueries(): URLSearchParams[] {
  return vi
    .mocked(fetch)
    .mock.calls.map(([r]) => new URL((r as Request).url))
    .filter((u) => u.pathname === "/api/dashboard")
    .map((u) => u.searchParams);
}

test("the KPI tiles give the month's figures and how spending moved", async () => {
  api();
  render(<TestApp path="/" />);

  const spent = await screen.findByRole("region", { name: "Spent" });
  expect(spent).toHaveTextContent("€1,621");
  expect(spent).toHaveTextContent("+16% vs last month");
  expect(spent).toHaveTextContent("+8% vs 12-month average");
  expect(screen.getByRole("region", { name: "Income" })).toHaveTextContent("€2,519");
  expect(screen.getByRole("region", { name: "Net" })).toHaveTextContent("+€898");
  expect(screen.getByRole("region", { name: "Savings rate" })).toHaveTextContent("36%");
});

test("the to-categorise tile links to those transactions", async () => {
  api();
  render(<TestApp path="/" />);

  const tile = await screen.findByRole("region", { name: "To categorise" });
  expect(tile).toHaveTextContent("10");
  expect(within(tile).getByRole("link", { name: /Categorise them/ })).toHaveAttribute(
    "href",
    "/transactions?category=none&from=2026-03-01&to=2026-03-31",
  );
});

test("a change cannot be computed from nothing", async () => {
  api({
    ...dashboard,
    kpis: {
      ...dashboard.kpis,
      spent_change_vs_previous: null,
      spent_change_vs_average: null,
      savings_rate: null,
    },
  });
  render(<TestApp path="/" />);

  const spent = await screen.findByRole("region", { name: "Spent" });
  expect(spent).toHaveTextContent("Nothing to compare with yet");
  expect(screen.getByRole("region", { name: "Savings rate" })).toHaveTextContent(
    "No income this month",
  );
});

test("every chart has a table with its values", async () => {
  api();
  render(<TestApp path="/" />);

  const byCategory = await screen.findByRole("table", { name: "Spending by category, Mar 2026" });
  expect(within(byCategory).getByRole("row", { name: /Housing/ })).toHaveTextContent("€850");
  expect(within(byCategory).getByRole("row", { name: /Housing/ })).toHaveTextContent("52%");
  const months = screen.getByRole("table", { name: "Spending and income, last 12 months" });
  expect(within(months).getAllByRole("row")).toHaveLength(13);
  const pace = screen.getByRole("table", { name: "Spending so far against the budget pace" });
  expect(within(pace).getAllByRole("row").at(-1)).toHaveTextContent("€1,500");
  expect(within(pace).getAllByRole("row").at(-1)).toHaveTextContent("€1,800");
});

test("choosing a month refetches it", async () => {
  api();
  render(<TestApp path="/" />);

  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(await screen.findByLabelText("Month"), { target: { value: "2026-02" } });

  await vi.waitFor(() => expect(dashboardQueries().at(-1)?.get("month")).toBe("2026-02"));
});

test("a household without transactions is pointed to the first import", async () => {
  api({
    ...dashboard,
    kpis: { ...dashboard.kpis, spent: "0.00", income: "0.00", net: "0.00", savings_rate: null },
    top_categories: [],
    to_categorise: { count: 0, spent: "0.00" },
    monthly: monthly.map((m) => ({ ...m, spent: "0.00", income: "0.00" })),
  });
  render(<TestApp path="/" />);

  expect(await screen.findByText(/No transactions yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to Accounts" })).toHaveAttribute("href", "/accounts");
});
