import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { thisMonth } from "../lib/months";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import {
  bakery,
  groceries,
  monthOf,
  rent,
  spendingCategories,
  summaryOf,
  supermarket,
} from "./fixtures";

beforeEach(() => localStorage.setItem("kwak-getting-started-hidden", "1"));
afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const month = thisMonth();

const wealth = (lines: number) => ({
  months: [month],
  categories: [
    {
      id: "c-stocks",
      name: "Stocks",
      kind: "asset",
      colour: "stocks",
      subtotals: ["8400.00"],
      share: "1.0000",
      lines: Array.from({ length: lines }, (_, i) => ({
        id: `w${i}`,
        name: "PEA",
        owner_id: owner.id,
        owner_name: "Wilson",
        visibility: "shared",
        closed_from: null,
        cells: [{ amount: "8400.00", carried: false }],
        share: "1.0000",
      })),
    },
  ],
  gross: ["8400.00"],
  debts: ["0.00"],
  net: ["8400.00"],
  change: ["650.00"],
  change_ratio: ["0.0838"],
});

type Handler = (body: unknown, url: URL) => Response;

function api(extra: Record<string, Handler> = {}, lines = [bakery, supermarket]) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/spending/month": () => Response.json(summaryOf(month)),
    "GET /api/spending/lines": () => Response.json(monthOf(month, lines)),
    "GET /api/spending/categories": () => Response.json(spendingCategories),
    "GET /api/spending/fixed/occurrences": () => Response.json([{ ...rent, due: `${month}-05` }]),
    "GET /api/wealth/matrix": () => Response.json(wealth(0)),
    ...extra,
  });
}

test("the month's figures say how spending moved and what is left", async () => {
  api();
  render(<TestApp path="/" />);

  const spent = await screen.findByRole("region", { name: "Spent" });
  expect(spent).toHaveTextContent("€100");
  expect(spent).toHaveTextContent("-10% vs last month");
  expect(spent).toHaveTextContent("+11% vs 12-month average");
  expect(screen.getByRole("region", { name: "Saved" })).toHaveTextContent("€200");
  const rest = screen.getByRole("region", { name: "Rest" });
  expect(rest).toHaveTextContent("+€2,700");
  expect(rest).toHaveTextContent("+€1,750 once the fixed expenses below are paid");
  expect(screen.getByRole("region", { name: "Savings rate" })).toHaveTextContent("97%");
});

test("the month so far shows each target's progress and opens its lines", async () => {
  api();
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: /^Spending targets, / });
  expect(section).toHaveTextContent("€43 of €50 · €8 left");
  expect(section).toHaveTextContent("Watch · 85% used");
  expect(section).toHaveTextContent("Pace: 71% of the month gone");
  expect(
    within(section).getByRole("link", { name: "Lines of Groceries this month" }),
  ).toHaveAttribute("href", `/spending?month=${month}&category=${groceries.id}`);
});

test("the savings objectives have their own section, below the spending targets", async () => {
  api();
  render(<TestApp path="/" />);

  const spending = await screen.findByRole("region", { name: /^Spending targets, / });
  const section = screen.getByRole("region", { name: /^Savings targets, / });
  expect(spending).not.toHaveTextContent("Savings");
  expect(section).toHaveTextContent("Targets this month: savings");
  expect(section).toHaveTextContent("€200 of €500 saved · €300 to go");
  expect(section).toHaveTextContent("In progress · 40% of the objective");
  expect(section).not.toHaveTextContent("Pace:");
  expect(
    within(section).getByRole("link", { name: "Lines of Savings this month" }),
  ).toHaveAttribute("href", `/spending?month=${month}&category=c-savings`);
  expect(spending.compareDocumentPosition(section) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

test("a savings objective reached, in French", async () => {
  api({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/spending/month": (_body, url) => {
      const summary = summaryOf(url.searchParams.get("month") ?? month);
      const reached = {
        ...summary.progress.savings[0],
        saved: "650.00",
        remaining: "-150.00",
        share: "1.3000",
        status: "reached",
      };
      return Response.json({ ...summary, progress: { ...summary.progress, savings: [reached] } });
    },
  });
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: /^Cibles d'épargne, / });
  expect(section).toHaveTextContent("Cibles du mois : épargne");
  expect(section).toHaveTextContent("150 € au-delà");
  expect(section).toHaveTextContent("Atteint · 130 % de l'objectif");
});

test("without any savings objective, the section says where to set one", async () => {
  api({
    "GET /api/spending/month": (_body, url) => {
      const summary = summaryOf(url.searchParams.get("month") ?? month);
      return Response.json({ ...summary, progress: { ...summary.progress, savings: [] } });
    },
  });
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: /^Savings targets, / });
  expect(section).toHaveTextContent("No savings category has a monthly objective this month.");
  expect(within(section).getByRole("link", { name: "Set them in Budget" })).toHaveAttribute(
    "href",
    "/budget",
  );
});

test("a fixed expense still to confirm is confirmed from the overview", async () => {
  const calls = api({
    "POST /api/spending/lines": (body) =>
      Response.json({ ...bakery, ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: "Fixed expenses to confirm" });
  expect(section).toHaveTextContent("Rent");
  expect(section).toHaveTextContent("€950.00");
  expect(section).toHaveTextContent("Rest at the end of the month: +€1,750");
  await userEvent.setup().click(within(section).getByRole("button", { name: "Confirm Rent" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/lines")?.body).toEqual({
      day: `${month}-05`,
      label: "Rent",
      amount: "-950.00",
      category_id: "c-housing",
      fixed_expense_id: "f-rent",
    }),
  );
});

test("the top categories and the last lines entered close the month", async () => {
  api();
  render(<TestApp path="/" />);

  const top = await screen.findByRole("region", { name: "Top categories" });
  expect(within(top).getByRole("link", { name: "Home" })).toBeInTheDocument();
  expect(top).toHaveTextContent("57%");
  const last = screen.getByRole("region", { name: "Last lines entered" });
  const items = within(last).getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("Supermarket");
  expect(items[0]).toHaveTextContent("Split");
  expect(items[1]).toHaveTextContent("Bakery");
});

test("a household with nothing entered is pointed to the lines", async () => {
  api(
    {
      "GET /api/spending/month": () =>
        Response.json({
          ...summaryOf(month),
          figures: {
            income: "0.00",
            spent: "0.00",
            saved: "0.00",
            rest: "0.00",
            savings_rate: null,
          },
        }),
    },
    [],
  );
  render(<TestApp path="/" />);

  expect(await screen.findByText(/Nothing entered yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Enter your lines" })).toHaveAttribute(
    "href",
    "/spending",
  );
});

test("the overview leads with net worth, in the wealth's scope", async () => {
  const asked: URL[] = [];
  api({
    "GET /api/wealth/matrix": (_body, url) => {
      asked.push(url);
      return Response.json(wealth(1));
    },
  });
  render(<TestApp path="/" />);

  const tile = await screen.findByRole("region", { name: "Net worth" });
  expect(tile).toHaveTextContent("€8,400");
  expect(tile).toHaveTextContent("+€650 · +8% vs last month");
  expect(asked[0]?.searchParams.get("scope")).toBe("household");
  expect(screen.getByLabelText("Wealth and goals")).toHaveValue("household");
});

test("the overview reads in French", async () => {
  api({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/" language="fr" />);

  const spent = await screen.findByRole("region", { name: "Dépenses" });
  expect(spent).toHaveTextContent(/100\s€/);
  expect(screen.getByRole("region", { name: "Dépenses fixes à confirmer" })).toHaveTextContent(
    /950,00\s€/,
  );
});

test("a past month's targets show no pace, and no one-off note either", async () => {
  api({
    "GET /api/spending/month": (_body, url) => {
      const asked = url.searchParams.get("month") ?? month;
      const summary = summaryOf(asked);
      return Response.json({
        ...summary,
        progress: {
          ...summary.progress,
          lines: summary.progress.lines.map((line) => ({ ...line, pace: null })),
        },
      });
    },
  });
  render(<TestApp path="/" />);

  fireEvent.change(await screen.findByLabelText("Month"), { target: { value: "2026-01" } });
  const section = await screen.findByRole("region", { name: "Spending targets, Jan 2026" });
  expect(section).toHaveTextContent("Groceries");
  expect(section).not.toHaveTextContent("Paid once in the month");
  expect(section).not.toHaveTextContent("Pace:");
  // A past month is not "this month so far".
  expect(screen.getByRole("region", { name: "Jan 2026 day by day" })).toBeInTheDocument();
});

test("the owner changes the warning threshold", async () => {
  const calls = api({
    "PATCH /api/household/settings": (body) => Response.json({ ...(body as object) }),
  });
  render(<TestApp path="/" />);

  const user = userEvent.setup();
  const section = await screen.findByRole("region", { name: /^Spending targets, / });
  expect(section).toHaveTextContent("Watch from 80% of a target");
  await user.click(within(section).getByRole("button", { name: "Change" }));
  const input = within(section).getByLabelText("Warning threshold (%)");
  await user.clear(input);
  await user.type(input, "40");
  await user.click(within(section).getByRole("button", { name: "Save" }));
  expect(within(section).getByText("Enter a whole number from 50 to 100.")).toBeVisible();

  await user.clear(input);
  await user.type(input, "90");
  await user.click(within(section).getByRole("button", { name: "Save" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
      warn_at: "0.90",
    }),
  );
});

test("without any wealth line, the overview shows no net worth", async () => {
  api();
  render(<TestApp path="/" />);
  await screen.findByRole("region", { name: "Spent" });
  expect(screen.queryByRole("region", { name: "Net worth" })).toBeNull();
});

test("the month's spending day by day is drawn against its targets, with its table", async () => {
  api();
  render(<TestApp path="/" />);

  const pace = await screen.findByRole("region", { name: "This month so far" });
  expect(pace).toHaveTextContent("Against a budget of €50 spread evenly over the month");
  const table = within(pace).getByRole("table", {
    name: "Spending so far against the budget pace",
  });
  // The header, then each day of the fixture (3) up to today: this month stops at today.
  const days = Math.min(new Date().getDate(), 3);
  expect(within(table).getAllByRole("row")).toHaveLength(1 + days);
});
