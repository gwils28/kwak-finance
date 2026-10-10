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
  previous,
  runningReview,
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

test("the budget page links to the review of the selected plan", async () => {
  api();
  render(<TestApp path="/budget" />);

  const link = await screen.findByRole("link", { name: "See the review" });
  expect(link).toHaveAttribute("href", "/budget/review?plan=p-current");
});

test("with no plan at all, the review says how to start", async () => {
  api(runningReview(), []);
  render(<TestApp path="/budget/review" />);

  expect(await screen.findByText(/No budget plan yet/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Go to the budget" })).toHaveAttribute("href", "/budget");
});
