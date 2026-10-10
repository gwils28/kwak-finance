import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { current } from "../budget/fixtures";
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
beforeEach(() => localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

const page = (total: number) => ({ items: [], total, limit: 1, offset: 0 });
const emptyDashboard = {
  month: "2026-03",
  kpis: {
    spent: "0.00",
    income: "0.00",
    net: "0.00",
    savings_rate: null,
    previous_spent: "0.00",
    average_spent: "0.00",
    spent_change_vs_previous: null,
    spent_change_vs_average: null,
  },
  top_categories: [],
  to_categorise: { count: 0, spent: "0.00" },
  monthly: [{ month: "2026-03", spent: "0.00", income: "0.00", by_category: [] }],
  cumulative: [],
  budget_target: null,
};

type Progress = {
  accounts?: number;
  transactions?: number;
  uncategorised?: number;
  plan?: boolean;
  members?: number;
};

function api({
  accounts = 0,
  transactions = 0,
  uncategorised = 0,
  plan = false,
  members = 1,
}: Progress) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/dashboard": () => Response.json(emptyDashboard),
    "GET /api/accounts": () =>
      Response.json(Array.from({ length: accounts }, (_, i) => ({ id: `a${i}` }))),
    "GET /api/transactions": (_body, url) =>
      Response.json(
        page(url.searchParams.get("uncategorised") === "true" ? uncategorised : transactions),
      ),
    "GET /api/budget/plans": () => Response.json(plan ? [current()] : []),
    "GET /api/household/members": () =>
      Response.json(Array.from({ length: members }, (_, i) => ({ id: `m${i}` }))),
  });
}

const checklist = () => screen.findByRole("region", { name: "Getting started" });
const step = (region: HTMLElement, name: RegExp) => within(region).getByRole("listitem", { name });

test("the overview's checklist ticks itself from the household's data", async () => {
  api({ accounts: 1, transactions: 40, uncategorised: 3 });
  render(<TestApp path="/" />);

  const region = await checklist();
  await vi.waitFor(() =>
    expect(step(region, /Add your bank accounts/)).toHaveAttribute("data-done", "true"),
  );
  expect(step(region, /Import a statement/)).toHaveAttribute("data-done", "true");
  expect(step(region, /Categorise your transactions/)).toHaveAttribute("data-done", "false");
  expect(step(region, /Set your monthly targets/)).toHaveAttribute("data-done", "false");
  expect(region).toHaveTextContent("2 of 5 done");
  expect(
    within(region).getByRole("link", { name: "Categorise your transactions" }),
  ).toHaveAttribute("href", "/transactions?category=none");
});

test("a plan with targets and a second member complete the checklist, which then disappears", async () => {
  api({ accounts: 1, transactions: 40, uncategorised: 0, plan: true, members: 2 });
  render(<TestApp path="/" />);

  expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  await vi.waitFor(() =>
    expect(
      vi.mocked(fetch).mock.calls.map(([r]) => new URL((r as Request).url).pathname),
    ).toContain("/api/household/members"),
  );
  expect(screen.queryByRole("region", { name: "Getting started" })).toBeNull();
});

test("the checklist can be hidden, and stays hidden", async () => {
  api({});
  const { unmount } = render(<TestApp path="/" />);

  await userEvent.setup().click(within(await checklist()).getByRole("button", { name: "Hide" }));
  expect(screen.queryByRole("region", { name: "Getting started" })).toBeNull();

  unmount();
  render(<TestApp path="/" />);
  expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "Getting started" })).toBeNull();
});

test("the guide is in the header and has a section per feature", async () => {
  api({});
  render(<TestApp path="/" />);

  await userEvent.setup().click(await screen.findByRole("link", { name: "Guide" }));

  expect(
    await screen.findByRole("heading", { level: 1, name: "Using Kwak Finance" }),
  ).toBeInTheDocument();
  const contents = screen.getByRole("navigation", { name: "Contents" });
  const entries = within(contents).getAllByRole("link");
  expect(entries.map((l) => l.textContent)).toEqual([
    "Getting started",
    "Accounts",
    "Importing statements",
    "Transactions",
    "Categories and rules",
    "Budget plans",
    "The budget table",
    "Plan review",
    "Overview",
    "Members and security",
  ]);
  expect(entries[5]).toHaveAttribute("href", "#plans");
  const plans = screen.getByRole("region", { name: "Budget plans" });
  expect(within(plans).getByRole("link", { name: "Open the budget" })).toHaveAttribute(
    "href",
    "/budget",
  );
});

test("the checklist links to the guide", async () => {
  api({});
  render(<TestApp path="/" />);

  expect(within(await checklist()).getByRole("link", { name: "Read the guide" })).toHaveAttribute(
    "href",
    "/guide",
  );
});

test("the guide reads in French", async () => {
  fakeApi({ "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/guide" language="fr" />);

  expect(
    await screen.findByRole("heading", { level: 1, name: "Utiliser Kwak Finance" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Plans budgétaires" })).toBeInTheDocument();
});
