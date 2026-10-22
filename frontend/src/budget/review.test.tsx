import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import type { PlanOut, ReviewOut } from "../api/generated";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import {
  comparison,
  cumulativeChart,
  current,
  currentLabel,
  matrix,
  planFlows,
  previous,
  runningReview,
  savingsReview,
} from "./fixtures";

beforeAll(() => {
  // Recharts measures its container; jsdom has no layout engine.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});
afterEach(() => vi.unstubAllGlobals());

function api(review: ReviewOut = runningReview(), plans: PlanOut[] = [previous(), current()]) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/budget/plans": () => Response.json(plans),
    "GET /api/budget/matrix": () => Response.json(matrix),
    "GET /api/budget/plans/p-current/review": () => Response.json(review),
    "GET /api/budget/plans/p-current/cumulative": () => Response.json(cumulativeChart()),
    "GET /api/budget/plans/p-current/flows": () => Response.json(planFlows()),
    "GET /api/budget/plans/p-current/comparison": (_body, url) =>
      Response.json(comparison(url.searchParams.get("against") === "p-other" ? other : previous())),
  });
}

const other = previous({ id: "p-other", period: "2025", start: "2025-01", end: "2025-12" });

function queries(path: string): URLSearchParams[] {
  return vi
    .mocked(fetch)
    .mock.calls.map(([r]) => new URL((r as Request).url))
    .filter((u) => u.pathname === path)
    .map((u) => u.searchParams);
}

test("during a plan, the review shows the time elapsed, the pace and the projection", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  expect(await screen.findByRole("heading", { name: "Plan review" })).toBeInTheDocument();
  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(summary).toHaveTextContent("51% of the plan elapsed");
  expect(summary).toHaveTextContent("Envelope€3,750");
  expect(summary).toHaveTextContent("Spent€2,057");
  expect(summary).toHaveTextContent("Expected by now€1,920");
  expect(summary).toHaveTextContent("Projected at the end€4,018");

  const table = screen.getByRole("table", { name: "Review by category" });
  const restaurants = within(table).getByRole("row", { name: /Restaurants/ });
  expect(restaurants).toHaveTextContent("€300");
  expect(restaurants).toHaveTextContent("€250");
  expect(within(restaurants).getByText("over")).toBeInTheDocument();
  expect(restaurants).toHaveTextContent("1 · 0 · 0");
});

test("drifting categories are ranked by projected overrun", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const drift = await screen.findByRole("region", { name: "Drifting categories" });
  const items = within(drift).getAllByRole("listitem");
  expect(items.map((i) => i.textContent)).toEqual([
    expect.stringMatching(/^Restaurants.*\+€188/),
    expect.stringMatching(/^Food.*\+€167/),
  ]);
});

test("spending left to categorise makes the review provisional", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const warning = await screen.findByText(/provisional/);
  expect(warning).toHaveTextContent("€40");
  const link = screen.getByRole("link", { name: "Categorise them" });
  expect(link.getAttribute("href")).toMatch(/^\/transactions\?category=none&from=/);
});

test("once over, the review gives the final result with the planned savings", async () => {
  api(runningReview({ elapsed: "1.0000", finished: true, drifting: [], provisional: false }));
  render(<TestApp path="/budget/review?plan=p-current" />);

  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(summary).toHaveTextContent("Final result");
  expect(summary).toHaveTextContent("Savings€343");
  expect(summary).toHaveTextContent("Planned savings€3,450");
  expect(summary).not.toHaveTextContent("Projected");
  expect(screen.queryByRole("region", { name: "Drifting categories" })).toBeNull();
});

test("the transfers crossing the scope show next to the income", async () => {
  api(runningReview({ paid_in: "1100.00", paid_out: "0.00" }));
  render(<TestApp path="/budget/review?plan=p-current" />);

  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(summary).toHaveTextContent("Paid in from other accounts€1,100");
  expect(summary).not.toHaveTextContent("Paid out to other accounts");
});

test("a plan closed early is labelled so, with its reason", async () => {
  const closed = current({ closed_early: true, close_reason: "job loss", editable: false });
  api(runningReview({ plan: closed }), [closed]);
  render(<TestApp path="/budget/review?plan=p-current" />);

  expect(await screen.findByText(/Closed early after/)).toBeInTheDocument();
  expect(screen.getByText("Reason: job loss")).toBeInTheDocument();
});

test("the gap chart shows the projected gap, as the status does", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const table = await screen.findByRole("table", { name: "Projected gap by category" });
  const rows = within(table)
    .getAllByRole("row")
    .slice(1)
    .map((r) => r.textContent);
  // Projection against the envelope, as the status: categories without a target have no gap.
  expect(rows).toEqual(["Food+14%", "Restaurants+63%", "Housing-2%"]);
});

test("the cumulative chart is in total, or for one category", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const chart = await screen.findByRole("region", { name: "Cumulative spending" });
  await userEvent.setup().selectOptions(within(chart).getByLabelText("Category"), "c-food");

  await vi.waitFor(() =>
    expect(
      queries("/api/budget/plans/p-current/cumulative").map((q) => q.get("category_id")),
    ).toEqual([null, "c-food"]),
  );
});

test("the plan is compared with the previous one, or another chosen", async () => {
  api(runningReview(), [other, previous(), current()]);
  render(<TestApp path="/budget/review?plan=p-current" />);

  const section = await screen.findByRole("region", { name: "Comparison" });
  const food = await within(section).findByRole("row", { name: /Food/ });
  expect(food).toHaveTextContent("€358");
  expect(food).toHaveTextContent("€455");
  expect(food).toHaveTextContent("+€97");
  expect(food).toHaveTextContent("+27%");

  await userEvent.setup().selectOptions(within(section).getByLabelText("Compare with"), "p-other");
  await vi.waitFor(() =>
    expect(queries("/api/budget/plans/p-current/comparison").at(-1)?.get("against")).toBe(
      "p-other",
    ),
  );
});

test("without a plan in the address, the review shows this month's plan", async () => {
  api();
  render(<TestApp path="/budget/review" />);

  expect(await screen.findByLabelText("Plan")).toHaveDisplayValue(new RegExp(`^${currentLabel}`));
  await vi.waitFor(() => expect(queries("/api/budget/plans/p-current/review")).toHaveLength(1));
});

test("with no plan at all, the review says how to start", async () => {
  api(runningReview(), []);
  render(<TestApp path="/budget/review" />);

  expect(await screen.findByText(/No budget plan yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to the budget" })).toHaveAttribute("href", "/budget");
});

test("the flows show where the plan's money came from and went, in a table too", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const section = await screen.findByRole("region", { name: "Money flows" });
  const table = await within(section).findByRole("table", { name: "Money flows" });
  const rows = within(table)
    .getAllByRole("row")
    .slice(1)
    .map((r) => r.textContent);
  // Spending is judged on its category's status: Housing on target, Food over.
  expect(rows).toEqual([
    "InSalary€7,80096%",
    "InPaid in from other accounts€3004%",
    "OutHousing€3,72046%within the target",
    "OutFood€6007%over the target",
    "OutTo categorise€801%",
    "OutSaved€1,50019%",
    "OutUnallocated€2,20027%",
  ]);
  const legend = within(section).getByRole("list", { name: "Colours" });
  expect(
    within(legend)
      .getAllByRole("listitem")
      .map((i) => i.textContent),
  ).toEqual([
    "Money in",
    "Spending within the target",
    "Spending over the target",
    "Savings",
    "Unallocated and transfers",
  ]);
});

test("savings below their objective are flagged in the flows", async () => {
  api(savingsReview());
  render(<TestApp path="/budget/review?plan=p-current" />);

  const section = await screen.findByRole("region", { name: "Money flows" });
  const table = await within(section).findByRole("table", { name: "Money flows" });
  expect(within(table).getByRole("row", { name: /Saved/ })).toHaveTextContent(
    "below the objective",
  );
  expect(within(section).getByRole("list", { name: "Colours" })).toHaveTextContent(
    "Savings below the objective",
  );
});

test("the flows can detail the spending by subcategory", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);

  const section = await screen.findByRole("region", { name: "Money flows" });
  await userEvent.setup().click(within(section).getByLabelText("Detail the subcategories"));

  const table = within(section).getByRole("table", { name: "Money flows" });
  expect(table).toHaveTextContent("Rent€3,450");
  expect(table).toHaveTextContent("Energy€270");
  expect(table).not.toHaveTextContent("Housing");
});

test("the flows follow the accounts chosen", async () => {
  api();
  render(<TestApp path="/budget/review?plan=p-current" />);
  await screen.findByRole("region", { name: "Money flows" });
  expect(queries("/api/budget/plans/p-current/flows").at(-1)?.get("scope")).toBe("household");
});

test("savings objectives have their own section, and one falling behind drifts", async () => {
  api(savingsReview());
  render(<TestApp path="/budget/review?plan=p-current" />);

  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(summary).toHaveTextContent("Savings objectives€900");

  const table = screen.getByRole("table", { name: "Review by category" });
  const section = within(table).getByRole("rowgroup", { name: "Savings & investments" });
  const investments = within(section).getByRole("row", { name: /Investments/ });
  expect(within(investments).getByText("behind")).toBeInTheDocument();
  expect(within(section).getByRole("row", { name: /Total saved/ })).toHaveTextContent("€250");
  // The section names its own columns: saved, not spent; months ahead, not over.
  expect(
    within(section)
      .getAllByRole("columnheader")
      .map((h) => h.textContent),
  ).toEqual([
    "Category",
    "Monthly objective",
    "Objective over the plan",
    "Saved",
    "Gap",
    "Expected",
    "Status",
    "Months ahead · on · behind",
  ]);
  // Savings never enter the spending total.
  expect(within(table).getByRole("rowheader", { name: "Total" }).closest("tr")).toHaveTextContent(
    "€2,057",
  );

  const drift = screen.getByRole("region", { name: "Drifting categories" });
  expect(within(drift).getAllByRole("listitem").at(-1)).toHaveTextContent(
    "Investments: €150 behind, €750 projected for an objective of €900",
  );
});

test("the comparison lists the savings objectives apart, with their own total", async () => {
  const saving = {
    ...comparison(previous()).rows[0],
    category_id: "c-pea",
    name: "Investments",
    target_a: "200.00",
    target_b: "300.00",
    average_a: "180.00",
    average_b: "250.00",
    change: "70.00",
    change_ratio: "0.3889",
    savings: true,
  };
  fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/budget/plans": () => Response.json([previous(), current()]),
    "GET /api/budget/plans/p-current/review": () => Response.json(savingsReview()),
    "GET /api/budget/plans/p-current/cumulative": () => Response.json(cumulativeChart()),
    "GET /api/budget/plans/p-current/flows": () => Response.json(planFlows()),
    "GET /api/budget/plans/p-current/comparison": () => {
      const data = comparison(previous());
      const total = { ...saving, category_id: null, name: "Total saved" };
      return Response.json({ ...data, rows: [...data.rows, saving, total] });
    },
  });
  render(<TestApp path="/budget/review?plan=p-current" />);

  const section = await screen.findByRole("region", { name: "Comparison" });
  const rows = (await within(section).findAllByRole("row")).map((r) => r.textContent);
  expect(rows.slice(-3)).toEqual([
    "Savings & investments",
    expect.stringMatching(/^Investments€200€300€180€250\+€70/),
    expect.stringMatching(/^Total saved/),
  ]);
});
