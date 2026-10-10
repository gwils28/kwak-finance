import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import type { PlanOut } from "../api/generated";
import { nextPeriod, periodText } from "../lib/plans";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { current, currentLabel as label, matrix, months, quarter, start } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

function api(plans: PlanOut[], extra: Record<string, (body: unknown) => Response> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/budget/matrix": () => Response.json(matrix),
    "GET /api/budget/plans": () => Response.json(plans),
    ...extra,
  });
}

const panel = async () => screen.findByRole("region", { name: "Budget plan" });

test("the plan covering this month is shown and its targets are edited in the matrix", async () => {
  const calls = api([current()], {
    "PUT /api/budget/plans/p-current/targets/c-groceries": () => Response.json(current()),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  expect(within(section).getByLabelText("Plan")).toHaveDisplayValue(new RegExp(`^${label}`));
  expect(section).toHaveTextContent(/Targets can be changed until/);
  expect(
    await screen.findByRole("columnheader", { name: `Monthly target · ${label}` }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Monthly target for Bakery and coffee")).toHaveValue("60");
  expect(screen.getByLabelText("Monthly target for Food")).toHaveAttribute(
    "placeholder",
    "€60 (sum)",
  );

  await userEvent.setup().type(screen.getByLabelText("Monthly target for Groceries"), "300{Enter}");

  await vi.waitFor(() =>
    expect(
      calls.find((c) => c.route === "PUT /api/budget/plans/p-current/targets/c-groceries")?.body,
    ).toEqual({ amount: "300.00" }),
  );
});

test("a locked plan's targets are read only and change by closing it early", async () => {
  const calls = api([current({ editable: false })], {
    "POST /api/budget/plans/p-current/close": () =>
      Response.json(current({ id: "p-rest", start: months[1] as string })),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  expect(section).toHaveTextContent(/Targets locked since/);
  await screen.findByRole("table", { name: "Budget by category and month" });
  expect(screen.queryByLabelText("Monthly target for Groceries")).toBeNull();
  expect(screen.getByRole("row", { name: /Bakery and coffee/ })).toHaveTextContent("€60");
  expect(within(section).queryByRole("button", { name: "Delete plan" })).toBeNull();

  const user = userEvent.setup();
  await user.click(within(section).getByRole("button", { name: "Close early" }));
  await user.selectOptions(
    within(section).getByLabelText("Last month of this plan"),
    months[0] as string,
  );
  await user.type(within(section).getByLabelText("Reason (optional)"), "job loss");
  await user.click(
    within(section).getByRole("button", { name: "Close and create the replacement" }),
  );

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/budget/plans/p-current/close")?.body).toEqual({
      last_month: months[0],
      reason: "job loss",
    }),
  );
});

test("a plan closed early says so, with its reason", async () => {
  api([current({ editable: false, closed_early: true, end: start, close_reason: "job loss" })]);
  render(<TestApp path="/budget" />);

  const section = await panel();
  expect(section).toHaveTextContent(/Closed early after/);
  expect(section).toHaveTextContent("Reason: job loss");
});

test("without a plan, the page offers to create this quarter's", async () => {
  const calls = api([], {
    "POST /api/budget/plans": () => Response.json(current(), { status: 201 }),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  expect(section).toHaveTextContent(/No budget plan yet/);
  expect(screen.queryByLabelText("Monthly target for Groceries")).toBeNull();

  const user = userEvent.setup();
  await user.click(within(section).getByRole("button", { name: "New plan" }));
  expect(within(section).getByLabelText("Length")).toHaveValue("quarter");
  await user.click(within(section).getByRole("button", { name: "Create the plan" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/budget/plans")?.body).toEqual({
      period: periodText(quarter),
    }),
  );
});

test("a new plan follows the latest one, and can cover a year", async () => {
  const calls = api([current()], {
    "POST /api/budget/plans": () => Response.json(current(), { status: 201 }),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  const user = userEvent.setup();
  await user.click(within(section).getByRole("button", { name: "New plan" }));
  const next = nextPeriod(quarter);
  expect(within(section).getByLabelText("Which one")).toHaveValue(String(next.number));
  expect(within(section).getByLabelText("Year")).toHaveValue(next.year);

  await user.selectOptions(within(section).getByLabelText("Length"), "year");
  expect(within(section).queryByLabelText("Which one")).toBeNull();
  await user.click(within(section).getByRole("button", { name: "Create the plan" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/budget/plans")?.body).toEqual({
      period: String(next.year),
    }),
  );
});

test("an editable plan is deleted once confirmed", async () => {
  const calls = api([current()], {
    "DELETE /api/budget/plans/p-current": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  const user = userEvent.setup();
  await user.click(within(section).getByRole("button", { name: "Delete plan" }));
  expect(calls.some((c) => c.route.startsWith("DELETE"))).toBe(false);
  await user.click(within(section).getByRole("button", { name: "Confirm deletion" }));

  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "DELETE /api/budget/plans/p-current")).toBe(true),
  );
});

test("the expected income and the note are saved when leaving the field", async () => {
  const calls = api([current()], {
    "PATCH /api/budget/plans/p-current": () => Response.json(current()),
  });
  render(<TestApp path="/budget" />);

  const section = await panel();
  const user = userEvent.setup();
  await user.type(within(section).getByLabelText("Expected monthly income"), "2 500{Tab}");
  await user.type(within(section).getByLabelText("Note"), "new job{Tab}");

  await vi.waitFor(() =>
    expect(
      calls.filter((c) => c.route === "PATCH /api/budget/plans/p-current").map((c) => c.body),
    ).toEqual([{ expected_income: "2500.00" }, { note: "new job" }]),
  );
});

test("a locked plan's expected income cannot change, its note can", async () => {
  api([current({ editable: false, expected_income: "2500.00" })]);
  render(<TestApp path="/budget" />);

  const section = await panel();
  expect(within(section).getByLabelText("Expected monthly income")).toBeDisabled();
  expect(within(section).getByLabelText("Note")).toBeEnabled();
});

test("periods read in French", async () => {
  api([current()], { "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }) });
  render(<TestApp path="/budget" language="fr" />);

  const section = await screen.findByRole("region", { name: "Plan budgétaire" });
  expect(within(section).getByLabelText("Plan")).toHaveDisplayValue(
    new RegExp(`^T${quarter.number} ${quarter.year}`),
  );
});
