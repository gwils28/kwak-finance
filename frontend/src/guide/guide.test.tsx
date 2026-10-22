import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, expect, test, vi } from "vitest";
import { thisMonth } from "../lib/months";
import { bakery, monthOf, spendingCategories, summaryOf } from "../spending/fixtures";
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

type Progress = {
  /** "lastMonth": income lines last month, none yet this month. */
  income?: boolean | "lastMonth";
  lines?: boolean;
  fixed?: boolean;
  plan?: boolean;
  members?: number;
  goal?: boolean;
};

function api({
  income = false,
  lines = false,
  fixed = false,
  plan = false,
  members = 1,
  goal = false,
}: Progress) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/spending/month": () => {
      const summary = summaryOf(thisMonth());
      // The month's income is its income lines: none entered, none.
      return Response.json(
        income === true
          ? summary
          : {
              ...summary,
              figures: { ...summary.figures, income: "0.00" },
              previous: { ...summary.previous, income: income ? "3000.00" : "0.00" },
              average: null,
            },
      );
    },
    "GET /api/spending/categories": () => Response.json(spendingCategories),
    "GET /api/spending/fixed/occurrences": () => Response.json([]),
    "GET /api/spending/lines": () => Response.json(monthOf(thisMonth(), lines ? [bakery] : [])),
    "GET /api/spending/fixed": () => Response.json(fixed ? [{ id: "f1" }] : []),
    "GET /api/spending/targets": () =>
      Response.json(
        plan ? [{ category_id: "c-groceries", from_month: "2026-01", amount: "50.00" }] : [],
      ),
    "GET /api/household/members": () =>
      Response.json(Array.from({ length: members }, (_, i) => ({ id: `m${i}` }))),
    "GET /api/goals": () =>
      Response.json({
        goals: [],
        closed: goal ? [{ tier: "short", precaution: true }] : [],
        pyramid: [],
      }),
  });
}

const checklist = () => screen.findByRole("region", { name: "Getting started" });
const step = (region: HTMLElement, name: RegExp) => within(region).getByRole("listitem", { name });

test("the overview's checklist ticks itself from the household's data", async () => {
  api({ income: true, lines: true });
  render(<TestApp path="/" />);

  const region = await checklist();
  await vi.waitFor(() =>
    expect(step(region, /Enter this month's income/)).toHaveAttribute("data-done", "true"),
  );
  expect(step(region, /Enter your first lines/)).toHaveAttribute("data-done", "true");
  expect(step(region, /Add your fixed expenses/)).toHaveAttribute("data-done", "false");
  expect(step(region, /Set your monthly targets/)).toHaveAttribute("data-done", "false");
  expect(step(region, /Set your emergency fund/)).toHaveAttribute("data-done", "false");
  expect(region).toHaveTextContent("2 of 6 done");
  expect(within(region).getByRole("link", { name: "Add your fixed expenses" })).toHaveAttribute(
    "href",
    "/spending/fixed",
  );
});

test("the income step stays done at the start of a month, before its salary line", async () => {
  api({ income: "lastMonth", lines: true });
  render(<TestApp path="/" />);
  const region = await checklist();
  await vi.waitFor(() =>
    expect(step(region, /Enter this month's income/)).toHaveAttribute("data-done", "true"),
  );
});

test("a plan with targets and a second member complete the checklist, which then disappears", async () => {
  api({ income: true, lines: true, fixed: true, plan: true, members: 2, goal: true });
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
    "Entering lines",
    "Fixed expenses",
    "Categories",
    "Budget",
    "The year",
    "Overview",
    "Wealth",
    "Goals",
    "Reports",
    "Members and security",
  ]);
  expect(entries[4]).toHaveAttribute("href", "#budget");
  const lines = screen.getByRole("region", { name: "Entering lines" });
  expect(within(lines).getByRole("link", { name: "Open the lines" })).toHaveAttribute(
    "href",
    "/spending",
  );
  const budget = screen.getByRole("region", { name: "Budget" });
  expect(within(budget).getByRole("link", { name: "Open the budget" })).toHaveAttribute(
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
  expect(screen.getByRole("region", { name: "Saisir les lignes" })).toBeInTheDocument();
});
