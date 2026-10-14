import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

const plain = (text: string | null) => text?.replace(/[\u00a0\u202f]/g, " ");

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
    paid_in: "0.00",
    paid_out: "0.00",
    net: "897.61",
    saved: "0.00",
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

const line = (extra: object) => ({
  parent_id: null,
  spent: "0.00",
  target: "100.00",
  remaining: "100.00",
  share: "0.0000",
  status: "on_track",
  pace: "0.4839",
  ...extra,
});
const progress = {
  month: "2026-03",
  plan: "2026-Q1",
  warn_at: "0.80",
  lines: [
    line({
      category_id: "c-leisure",
      name: "Leisure",
      spent: "130.00",
      remaining: "-30.00",
      share: "1.3000",
      status: "over",
    }),
    line({
      category_id: "c-rent",
      name: "Rent",
      parent_id: "c-housing",
      spent: "850.00",
      target: "850.00",
      remaining: "0.00",
      share: "1.0000",
      status: "watch",
      pace: null,
    }),
    line({
      category_id: "c-food",
      name: "Food",
      spent: "406.40",
      target: "500.00",
      remaining: "93.60",
      share: "0.8128",
      status: "watch",
    }),
  ],
};

function api(
  data: unknown = dashboard,
  accounts: unknown[] = [],
  extra: Record<string, (body: unknown) => Response> = {},
) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/dashboard": () => Response.json(data),
    "GET /api/budget/progress": () => Response.json(progress),
    "GET /api/accounts": () => Response.json(accounts),
    ...extra,
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
    "/transactions?category=none&month=2026-03",
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

test("the month's top categories lead to its report", async () => {
  api();
  render(<TestApp path="/" />);

  const top = await screen.findByRole("region", { name: "Top categories" });
  const items = within(top).getAllByRole("listitem");
  // The share is read out with what it is a share of.
  expect(items[0]).toHaveTextContent("Housing€85052% of spending");
  expect(items[1]).toHaveTextContent("Food€40625% of spending");
  expect(within(top).getByRole("link", { name: "See the month's report" })).toHaveAttribute(
    "href",
    "/reports?start=2026-03&end=2026-03",
  );
});

test("the pace chart has a table, and the months over time are left to the reports", async () => {
  api();
  render(<TestApp path="/" />);

  const pace = await screen.findByRole("table", {
    name: "Spending so far against the budget pace",
  });
  expect(within(pace).getAllByRole("row").at(-1)).toHaveTextContent("€1,500");
  expect(within(pace).getAllByRole("row").at(-1)).toHaveTextContent("€1,800");
  expect(screen.queryByRole("table", { name: /last 12 months/ })).not.toBeInTheDocument();
  expect(screen.queryByRole("table", { name: /Spending by category/ })).not.toBeInTheDocument();
});

test("choosing a month refetches it", async () => {
  api();
  render(<TestApp path="/" />);

  // jsdom cannot type into <input type="month">: set the value as the picker would.
  fireEvent.change(await screen.findByLabelText("Month"), { target: { value: "2026-02" } });

  await vi.waitFor(() => expect(dashboardQueries().at(-1)?.get("month")).toBe("2026-02"));
});

test("the joint accounts can be looked at alone, once the household has one", async () => {
  api(dashboard, [{ id: "a1", type: "checking", visibility: "joint" }]);
  render(<TestApp path="/" />);

  const scope = await screen.findByLabelText("Accounts");
  await screen.findByRole("option", { name: "Joint accounts" });
  fireEvent.change(scope, { target: { value: "joint" } });

  await vi.waitFor(() => expect(dashboardQueries().at(-1)?.get("scope")).toBe("joint"));
});

test("without a joint account, the scope offers the household or mine only", async () => {
  api();
  render(<TestApp path="/" />);

  const scope = await screen.findByLabelText("Accounts");
  expect(
    within(scope)
      .getAllByRole("option")
      .map((o) => o.textContent),
  ).toEqual(["Household", "Only mine"]);
});

test("the net tile shows what was paid in or out by transfers crossing the scope", async () => {
  const kpis = { ...dashboard.kpis, paid_in: "0.00", paid_out: "1100.00", net: "1359.00" };
  api({ ...dashboard, kpis });
  render(<TestApp path="/" />);

  const tile = await screen.findByRole("region", { name: "Net" });
  expect(plain(tile.textContent)).toContain("-€1,100 paid out to other accounts");
  expect(tile).not.toHaveTextContent("paid in");
  expect(tile).not.toHaveTextContent("transfers excluded");
});

test("the net tile shows the part put in savings categories", async () => {
  api({ ...dashboard, kpis: { ...dashboard.kpis, saved: "300.00" } });
  render(<TestApp path="/" />);

  const tile = await screen.findByRole("region", { name: "Net" });
  expect(plain(tile.textContent)).toContain("of which €300 put in savings & investments");
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

test("the month's targets show each category's progress, its status and the pace", async () => {
  api();
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: "Targets, Mar 2026" });
  const items = await within(section).findAllByRole("listitem");
  expect(items.map((i) => within(i).getByRole("link").textContent)).toEqual([
    "Leisure",
    "Rent",
    "Food",
  ]);
  const [leisure, rent, food] = items as [HTMLElement, HTMLElement, HTMLElement];
  expect(plain(leisure.textContent)).toContain("€130 of €100 · €30 over");
  expect(leisure).toHaveTextContent("Over · 130% used");
  expect(rent).toHaveTextContent("Paid once in the month: no pace");
  expect(plain(food.textContent)).toContain("€94 left");
  expect(food).toHaveTextContent("Watch · 81% used");
  expect(food).toHaveTextContent("Pace: 48% of the month gone");
  expect(
    within(food).getByRole("link", { name: "Transactions of Food this month" }),
  ).toHaveAttribute("href", "/transactions?category=c-food&month=2026-03");
  expect(section).toHaveTextContent("Watch from 80% of a target");
});

test("a month outside any plan points to the budget", async () => {
  api(dashboard, [], {
    "GET /api/budget/progress": () => Response.json({ ...progress, plan: null, lines: [] }),
  });
  render(<TestApp path="/" />);

  const section = await screen.findByRole("region", { name: "Targets, Mar 2026" });
  expect(await within(section).findByText(/No budget plan covers this month/)).toBeInTheDocument();
  expect(within(section).getByRole("link", { name: "Create one in Budget" })).toHaveAttribute(
    "href",
    "/budget",
  );
});

test("the owner changes the warning threshold", async () => {
  const calls = api(dashboard, [], {
    "PATCH /api/household/settings": (body) => Response.json(body),
  });
  render(<TestApp path="/" />);

  const user = userEvent.setup();
  const section = await screen.findByRole("region", { name: "Targets, Mar 2026" });
  await user.click(await within(section).findByRole("button", { name: "Change" }));
  const field = within(section).getByLabelText("Warning threshold (%)");
  await user.clear(field);
  await user.type(field, "120");
  await user.click(within(section).getByRole("button", { name: "Save" }));
  expect(section).toHaveTextContent("Enter a whole number from 50 to 100.");

  await user.clear(field);
  await user.type(field, "90");
  await user.click(within(section).getByRole("button", { name: "Save" }));
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PATCH /api/household/settings")?.body).toEqual({
      warn_at: "0.90",
    }),
  );
});

const upcoming = {
  occurrences: [
    {
      item_id: "r1",
      due: "2026-03-03",
      expected: "-950.00",
      status: "late",
      transaction_id: null,
      enter_on: "2026-03-03",
      label: "LOYER",
      account_id: "a1",
      account_name: "Compte courant",
      category_id: null,
      estimated: false,
    },
    {
      item_id: "r3",
      due: "2026-03-28",
      expected: "2500.00",
      status: "upcoming",
      transaction_id: null,
      enter_on: "2026-03-13",
      label: "SALAIRE",
      account_id: "a1",
      account_name: "Compte courant",
      category_id: null,
      estimated: false,
    },
  ],
  current_balance: "984.01",
  projected_balance: "2534.01",
};

test("the overview lists what is still expected this month and the projected balance", async () => {
  const checking = { id: "a1", name: "Compte courant", institution: "SG", type: "checking" };
  const calls = api(dashboard, [checking], {
    "GET /api/recurring/upcoming": () => Response.json(upcoming),
    "PUT /api/recurring/r1/skips/2026-03-03": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/" />);

  const block = await screen.findByRole("region", { name: "Still expected this month" });
  expect(block).toHaveTextContent("Projected at month end€2,534");
  expect(block).toHaveTextContent("Balance today: €984");
  const [late, salary] = within(block).getAllByRole("listitem");
  expect(late).toHaveTextContent("3 Mar 2026LateLOYER");
  expect(salary).toHaveTextContent("€2,500.00");

  const user = userEvent.setup();
  await user.click(within(block).getByRole("button", { name: "Enter SALAIRE of 28 Mar 2026" }));
  const form = within(block).getByRole("form", { name: "New transaction" });
  expect(within(form).getByLabelText("Date")).toHaveValue("2026-03-13"); // the 28th is to come
  expect(within(form).getByRole("radio", { name: "Income" })).toBeChecked();

  await user.click(within(block).getByRole("button", { name: "Skip LOYER of 3 Mar 2026" }));
  expect(calls.map((c) => c.route)).toContain("PUT /api/recurring/r1/skips/2026-03-03");
});

test("the overview shows nothing expected without recurring items", async () => {
  api(dashboard, [], {
    "GET /api/recurring/upcoming": () =>
      Response.json({ occurrences: [], current_balance: "0.00", projected_balance: "0.00" }),
  });
  render(<TestApp path="/" />);

  await screen.findByRole("region", { name: "Spent" });
  expect(screen.queryByRole("region", { name: "Still expected this month" })).toBeNull();
});

test("a recurring transfer shows what it brings to the scope", async () => {
  const checking = { id: "a1", name: "Compte courant", institution: "SG", type: "checking" };
  const share = {
    ...upcoming.occurrences[1],
    item_id: "r3",
    due: "2026-03-20",
    expected: "-500.00",
    label: "",
    destination_account_id: "a2",
    destination_account_name: "Compte commun",
    amount_in_scope: "500.00",
  };
  api(dashboard, [checking], {
    "GET /api/recurring/upcoming": () => Response.json({ ...upcoming, occurrences: [share] }),
  });
  render(<TestApp path="/" />);

  const block = await screen.findByRole("region", { name: "Still expected this month" });
  const [item] = within(block).getAllByRole("listitem");
  expect(item).toHaveTextContent("Transfer to Compte commun");
  expect(item).toHaveTextContent("Compte courant → Compte commun");
  expect(item).toHaveTextContent("€500.00");
});

test("a recurring transfer within the scope shows its amount without a sign", async () => {
  const checking = { id: "a1", name: "Compte courant", institution: "SG", type: "checking" };
  const share = {
    ...upcoming.occurrences[1],
    item_id: "r3",
    expected: "-500.00",
    label: "",
    destination_account_id: "a2",
    destination_account_name: "Compte commun",
    amount_in_scope: "0.00",
  };
  api(dashboard, [checking], {
    "GET /api/recurring/upcoming": () => Response.json({ ...upcoming, occurrences: [share] }),
  });
  render(<TestApp path="/" />);

  const block = await screen.findByRole("region", { name: "Still expected this month" });
  const amount = within(block).getByText("€500.00");
  expect(amount).not.toHaveClass("text-positive");
});

test("a month without categorised spending says so, in French too", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    "GET /api/dashboard": () => Response.json({ ...dashboard, top_categories: [] }),
    "GET /api/budget/progress": () => Response.json(progress),
    "GET /api/accounts": () => Response.json([]),
  });
  render(<TestApp path="/" language="fr" />);

  const top = await screen.findByRole("region", { name: "Principales catégories" });
  expect(top).toHaveTextContent("Aucune dépense catégorisée ce mois-ci.");
  expect(within(top).getByRole("link", { name: "Voir le rapport du mois" })).toBeInTheDocument();
});
