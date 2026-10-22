import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";
import { bakery, groceries, home, rent, spendingHandlers, supermarket } from "./fixtures";

afterEach(() => vi.unstubAllGlobals());

type Handler = (body: unknown, url: URL) => Response | Promise<Response>;

function api(extra: Record<string, Handler> = {}, occurrences = [] as (typeof rent)[]) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    ...spendingHandlers([bakery, supermarket], occurrences),
    "POST /api/spending/lines": (body) =>
      Response.json({ ...bakery, id: "l9", ...(body as object), parts: [] }, { status: 201 }),
    ...extra,
  });
}

const PATH = "/spending?month=2026-10";

async function grid() {
  return screen.findByRole("table", { name: "Lines of Oct 2026" });
}

function rowOf(label: string): HTMLElement {
  const input = screen.getByDisplayValue(label);
  return input.closest("tr") as HTMLElement;
}

function newRow(): HTMLElement {
  const body = screen.getByRole("rowgroup", { name: "New line" });
  return within(body).getAllByRole("row")[0] as HTMLElement;
}

test("the month's lines are listed with its figures, a split line with its parts", async () => {
  api();
  render(<TestApp path={PATH} />);

  await grid();
  expect(screen.getByRole("heading", { name: "Oct 2026" })).toBeInTheDocument();
  await vi.waitFor(() => expect(screen.getByLabelText("Income")).toHaveValue("3000"));
  expect(await screen.findByText("€99.90")).toBeInTheDocument();
  expect(screen.getByText("€2,900.10")).toBeInTheDocument();

  const row = rowOf("Bakery");
  expect(within(row).getByLabelText("Amount")).toHaveValue("12.50");
  expect(within(row).getByLabelText("Category")).toHaveValue(groceries.id);
  const split = screen.getByRole("group", { name: "Split" });
  expect(within(split).getByLabelText("Part 1: Amount")).toHaveValue("30");
  expect(within(split).getByLabelText("Rest: Category")).toHaveValue(home.id);
  expect(within(split).getByText("takes the rest: €57.40")).toBeInTheDocument();
  // The line entered last is marked, and the header says when.
  expect(
    within(rowOf("Supermarket")).getByRole("img", { name: "Line entered last" }),
  ).toBeVisible();
  expect(screen.getByText(/Last entry: .*16\/10.*entered on 16\/10/)).toBeInTheDocument();
  expect(screen.getByText("2 lines")).toBeInTheDocument();
});

test("the empty row is saved with Enter, as an outflow, and a new one opens on the same date", async () => {
  const calls = api();
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const row = newRow();
  await user.clear(within(row).getByLabelText("Date"));
  await user.type(within(row).getByLabelText("Date"), "2026-10-20");
  await user.type(within(row).getByLabelText("Label"), "Pharmacy");
  await user.type(within(row).getByLabelText("Amount"), "8,90");
  await user.selectOptions(within(row).getByLabelText("Category"), home.id);
  await user.keyboard("{Enter}");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/lines")?.body).toEqual({
      day: "2026-10-20",
      label: "Pharmacy",
      amount: "-8.90",
      category_id: home.id,
      fixed_expense_id: null,
    }),
  );
  await vi.waitFor(() => expect(within(newRow()).getByLabelText("Label")).toHaveFocus());
  expect(within(newRow()).getByLabelText("Label")).toHaveValue("");
  expect(within(newRow()).getByLabelText("Date")).toHaveValue("2026-10-20");
});

test("an incomplete row is not saved: Enter goes to the missing cell", async () => {
  const calls = api();
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  await user.type(within(newRow()).getByLabelText("Label"), "Pharmacy{Enter}");

  expect(within(newRow()).getByLabelText("Amount")).toHaveFocus();
  expect(calls.some((c) => c.route === "POST /api/spending/lines")).toBe(false);
});

test("a line is changed in place: Enter saves it, Escape puts it back", async () => {
  const calls = api({
    "PUT /api/spending/lines/l1": (body) => Response.json({ ...bakery, ...(body as object) }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const amount = within(rowOf("Bakery")).getByLabelText("Amount");
  await user.clear(amount);
  await user.type(amount, "13{Escape}");
  expect(amount).toHaveValue("12.50");

  await user.clear(amount);
  await user.type(amount, "13{Enter}");
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/spending/lines/l1")?.body).toMatchObject({
      amount: "-13.00",
      category_id: groceries.id,
    }),
  );
});

test("a known label brings the category of last time, not the amount", async () => {
  api({
    "GET /api/spending/labels": () =>
      Response.json([{ label: "Boulangerie", category_id: groceries.id }]),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  await user.type(within(newRow()).getByLabelText("Label"), "boulangerie");

  await vi.waitFor(() =>
    expect(within(newRow()).getByLabelText("Category")).toHaveValue(groceries.id),
  );
  expect(within(newRow()).getByLabelText("Amount")).toHaveValue("");
});

test("the quick line saves a complete line straight away", async () => {
  const calls = api({
    "POST /api/spending/quick": () =>
      Response.json({
        day: "2026-10-21",
        amount: "-12.50",
        label: "boulangerie",
        category_id: groceries.id,
        category_word: null,
      }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Quick line"), "boulangerie 12,50 hier");
  expect(await screen.findByText(/21 Oct 2026 · boulangerie · €12.50 · Groceries/)).toBeVisible();
  await user.keyboard("{Enter}");

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/lines")?.body).toEqual({
      day: "2026-10-21",
      label: "boulangerie",
      amount: "-12.50",
      category_id: groceries.id,
      fixed_expense_id: null,
    }),
  );
  expect(screen.getByLabelText("Quick line")).toHaveValue("");
});

test("an incomplete quick line goes into the empty row, the missing cell focused", async () => {
  const calls = api({
    "POST /api/spending/quick": () =>
      Response.json({
        day: null,
        amount: "-45.00",
        label: "sncf",
        category_id: null,
        category_word: "trains",
      }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Quick line"), "45 sncf #trains");
  expect(await screen.findByText(/no category starts with “trains”/)).toBeVisible();
  await user.keyboard("{Enter}");

  await vi.waitFor(() => expect(within(newRow()).getByLabelText("Category")).toHaveFocus());
  expect(within(newRow()).getByLabelText("Label")).toHaveValue("sncf");
  expect(within(newRow()).getByLabelText("Amount")).toHaveValue("45");
  expect(calls.some((c) => c.route === "POST /api/spending/lines")).toBe(false);
});

test("a fixed expense due is confirmed with Enter, or skipped for the month", async () => {
  const calls = api(
    { "PUT /api/spending/fixed/f-rent/skips/2026-10": () => new Response(null, { status: 204 }) },
    [rent],
  );
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const due = screen.getByRole("rowgroup", { name: "Fixed expenses due this month" });
  const row = within(due).getByDisplayValue("Rent").closest("tr") as HTMLElement;
  await user.click(within(row).getByLabelText("Amount"));
  await user.keyboard("{Enter}");
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/lines")?.body).toEqual({
      day: "2026-10-05",
      label: "Rent",
      amount: "-950.00",
      category_id: "c-housing",
      fixed_expense_id: "f-rent",
    }),
  );

  await user.click(within(row).getByRole("button", { name: "Skip this month" }));
  await vi.waitFor(() =>
    expect(calls.some((c) => c.route === "PUT /api/spending/fixed/f-rent/skips/2026-10")).toBe(
      true,
    ),
  );
});

test("a deleted line can be put back from the message", async () => {
  const calls = api({ "DELETE /api/spending/lines/l1": () => new Response(null, { status: 204 }) });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Delete Bakery" }));
  expect(await screen.findByText("“Bakery” deleted.")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Undo" }));

  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "POST /api/spending/lines")?.body).toMatchObject({
      day: "2026-10-14",
      label: "Bakery",
      amount: "-12.50",
      category_id: groceries.id,
    }),
  );
});

test("the month's income is entered in the header", async () => {
  const calls = api({
    "PUT /api/spending/income/2026-10": (body) =>
      Response.json({ month: "2026-10", ...(body as object), carried: false }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const income = screen.getByLabelText("Income");
  await vi.waitFor(() => expect(income).toHaveValue("3000"));
  await user.clear(income);
  await user.type(income, "3 150,20{Enter}");
  await vi.waitFor(() =>
    expect(calls.find((c) => c.route === "PUT /api/spending/income/2026-10")?.body).toEqual({
      amount: "3150.20",
    }),
  );
});

test("a category filter shows only its lines, split ones included", async () => {
  api();
  render(<TestApp path={`${PATH}&category=${home.id}`} />);
  await grid();

  expect(screen.queryByDisplayValue("Bakery")).toBeNull();
  expect(screen.getByDisplayValue("Supermarket")).toBeInTheDocument();
  expect(screen.getByText("Only Home")).toBeVisible();
});

test("the grid reads in French", async () => {
  fakeApi({
    "GET /api/auth/me": () => Response.json({ ...owner, language: "fr" }),
    ...spendingHandlers([bakery]),
  });
  render(<TestApp path={PATH} language="fr" />);

  await screen.findByRole("table", { name: "Lignes de oct. 2026" });
  expect(within(rowOf("Bakery")).getByLabelText("Montant")).toHaveValue("12,50");
  expect(await screen.findByText(/99,90\s€/)).toBeInTheDocument();
  expect(screen.getByText("1 ligne")).toBeInTheDocument();
});

test("Enter pressed twice saves the row once", async () => {
  let release: () => void = () => {};
  const calls = api({
    "POST /api/spending/lines": async (body) => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return Response.json(
        { ...bakery, id: "l9", ...(body as object), parts: [] },
        { status: 201 },
      );
    },
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const row = newRow();
  await user.type(within(row).getByLabelText("Label"), "Pharmacy");
  await user.type(within(row).getByLabelText("Amount"), "8,90");
  await user.selectOptions(within(row).getByLabelText("Category"), home.id);
  await user.keyboard("{Enter}{Enter}");
  release();

  await vi.waitFor(() => expect(within(newRow()).getByLabelText("Label")).toHaveValue(""));
  expect(calls.filter((c) => c.route === "POST /api/spending/lines")).toHaveLength(1);
});

test("changing month with the keyboard keeps a row's unsaved changes, and never moves the income", async () => {
  const calls = api({
    "PUT /api/spending/income/2026-10": (body) =>
      Response.json({ month: "2026-10", ...(body as object), carried: false }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  const user = userEvent.setup();
  const label = within(rowOf("Bakery")).getByLabelText("Label");
  await user.type(label, "s");
  await user.keyboard("{Alt>}{PageDown}{/Alt}");
  expect(screen.getByRole("heading", { name: "Oct 2026" })).toBeInTheDocument();
  await user.keyboard("{Escape}");

  const income = screen.getByLabelText("Income");
  await vi.waitFor(() => expect(income).toHaveValue("3000"));
  await user.clear(income);
  await user.type(income, "2500");
  await user.keyboard("{Alt>}{PageDown}{/Alt}");
  expect(await screen.findByRole("heading", { name: "Nov 2026" })).toBeInTheDocument();
  expect(calls.some((c) => c.route === "PUT /api/spending/income/2026-11")).toBe(false);
});

test("a delete that fails says so", async () => {
  api({
    "DELETE /api/spending/lines/l1": () =>
      Response.json({ detail: "no such line" }, { status: 404 }),
  });
  render(<TestApp path={PATH} />);
  await grid();

  await userEvent.setup().click(screen.getByRole("button", { name: "Delete Bakery" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("No such line.");
});
