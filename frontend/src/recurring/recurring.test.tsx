import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { fakeApi, owner } from "../test/fakeApi";
import { TestApp } from "../test/TestApp";

afterEach(() => vi.unstubAllGlobals());

const checking = {
  id: "a1",
  name: "Compte courant",
  institution: "Société Générale",
  type: "checking",
  visibility: "shared",
  owner_id: owner.id,
  owner_name: "Wilson",
  opening_balance: "0.00",
  opening_date: "2026-01-01",
  closed_on: null,
  balance: "984.01",
};
const categories = [
  {
    id: "c-housing",
    name: "Housing",
    kind: "expense",
    parent_id: null,
    shift_day: null,
    one_off: true,
  },
  {
    id: "c-rent",
    name: "Rent",
    kind: "expense",
    parent_id: "c-housing",
    shift_day: null,
    one_off: null,
  },
];
const occurrence = (due: string, status: string, extra: object = {}) => ({
  item_id: "r1",
  due,
  expected: "-950.00",
  status,
  transaction_id: null,
  enter_on: due,
  ...extra,
});
const rent = {
  id: "r1",
  account_id: "a1",
  account_name: "Compte courant",
  category_id: "c-rent",
  category_name: "Rent",
  label: "LOYER",
  amount: "-950.00",
  frequency: "monthly",
  day: 3,
  start_on: "2026-01-01",
  end_on: null,
  estimated: false,
  paused: false,
  next: occurrence("2026-04-03", "upcoming", { enter_on: "2026-03-13" }),
  recent: [
    occurrence("2026-03-03", "late"),
    occurrence("2026-02-03", "skipped"),
    occurrence("2026-01-03", "fulfilled", { transaction_id: "t1" }),
  ],
};
const edf = {
  ...rent,
  id: "r2",
  label: "EDF",
  category_id: null,
  category_name: null,
  amount: "-80.00",
  day: 20,
  estimated: true,
  next: { ...occurrence("2026-03-20", "upcoming"), item_id: "r2", expected: "-85.00" },
  recent: [],
};
const netflix = {
  account_id: "a1",
  account_name: "Compte courant",
  label: "NETFLIX",
  amount: "-15.99",
  estimated: false,
  frequency: "monthly",
  day: 4,
  start_on: "2025-12-04",
  category_id: null,
  count: 4,
};

type Handler = (body: unknown) => Response;

function api(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([checking]),
    "GET /api/categories": () => Response.json(categories),
    "GET /api/recurring": () => Response.json([edf, rent]),
    "GET /api/recurring/suggestions": () => Response.json([netflix]),
    ...extra,
  });
}

test("the Recurring page opens from Transactions", async () => {
  api({ "GET /api/transactions": () => Response.json({ items: [], total: 0 }) });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Recurring" }));
  expect(await screen.findByRole("heading", { name: "Recurring" })).toBeInTheDocument();
});

test("items show their schedule, amount and next occurrence, late ones first", async () => {
  api();
  render(<TestApp path="/recurring" />);

  const table = await screen.findByRole("table", { name: "Recurring" });
  const [electricity, loyer] = within(table).getAllByRole("row").slice(1);
  expect(electricity).toHaveTextContent("EDF");
  expect(electricity).toHaveTextContent("Monthly, on the 20th");
  expect(electricity).toHaveTextContent("≈ -€85.00"); // the average of the last 3
  expect(electricity).toHaveTextContent("20 Mar 2026 Upcoming");
  expect(loyer).toHaveTextContent("Compte courant · Rent");
  expect(loyer).toHaveTextContent("Monthly, on the 3rd");
  expect(loyer).toHaveTextContent("3 Mar 2026 Late");
  expect(loyer).toHaveTextContent("3 Apr 2026 Upcoming");
});

test("enter it opens the manual entry pre-filled, category included", async () => {
  const calls = api({
    "POST /api/transactions": (body) =>
      Response.json({ id: "t9", ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Enter LOYER of 3 Mar 2026" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  expect(within(form).getByLabelText("Date")).toHaveValue("2026-03-03");
  expect(within(form).getByLabelText("Amount (€)")).toHaveValue("950.00");
  expect(within(form).getByLabelText("Label")).toHaveValue("LOYER");
  expect(within(form).getByLabelText("Category")).toHaveValue("c-rent");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/transactions")?.body).toEqual({
    account_id: "a1",
    booked_on: "2026-03-03",
    amount: "-950.00",
    label: "LOYER",
    category_id: "c-rent",
  });
});

test("a late occurrence can be skipped and a skipped one restored", async () => {
  const calls = api({
    "PUT /api/recurring/r1/skips/2026-03-03": () => new Response(null, { status: 204 }),
    "DELETE /api/recurring/r1/skips/2026-02-03": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "History of LOYER" }));
  const history = screen.getByRole("list", { name: "History of LOYER" });
  expect(within(history).getAllByRole("listitem")[2]).toHaveTextContent("Done");
  await user.click(within(history).getByRole("button", { name: "Skip LOYER of 3 Mar 2026" }));
  await user.click(within(history).getByRole("button", { name: "Restore LOYER of 3 Feb 2026" }));

  const routes = calls.map((c) => c.route);
  expect(routes).toContain("PUT /api/recurring/r1/skips/2026-03-03");
  expect(routes).toContain("DELETE /api/recurring/r1/skips/2026-02-03");
});

test("a new weekly item is saved with its weekday", async () => {
  const calls = api({
    "GET /api/recurring": () => Response.json([]),
    "POST /api/recurring": (body) =>
      Response.json({ ...rent, ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  expect(await screen.findByText(/No recurring items yet/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Add a recurring item" }));
  const form = screen.getByRole("form", { name: "New recurring item" });
  await user.type(within(form).getByLabelText("Label"), "Marché");
  await user.type(within(form).getByLabelText("Amount (€)"), "30");
  await user.click(within(form).getByLabelText(/Variable amount/));
  await user.selectOptions(within(form).getByLabelText("Frequency"), "weekly");
  await user.selectOptions(within(form).getByLabelText("Day of the week"), "Saturday");
  await user.clear(within(form).getByLabelText("From"));
  await user.type(within(form).getByLabelText("From"), "2026-03-01");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/recurring")?.body).toEqual({
    account_id: "a1",
    destination_account_id: null,
    category_id: null,
    label: "Marché",
    amount: "-30.00",
    frequency: "weekly",
    day: 5,
    start_on: "2026-03-01",
    end_on: null,
    estimated: true,
    paused: false,
  });
});

test("a suggestion is followed through the form, or dismissed", async () => {
  const calls = api({
    "POST /api/recurring": (body) =>
      Response.json({ ...rent, ...(body as object) }, { status: 201 }),
    "POST /api/recurring/suggestions/dismiss": () => new Response(null, { status: 204 }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  const suggestions = await screen.findByRole("region", { name: "Suggestions" });
  expect(suggestions).toHaveTextContent("Monthly, on the 4th · 4 times since 4 Dec 2025");
  await user.click(within(suggestions).getByRole("button", { name: "Follow NETFLIX" }));
  const form = screen.getByRole("form", { name: "New recurring item" });
  expect(within(form).getByLabelText("Day of the month")).toHaveValue(4);
  await user.click(within(form).getByRole("button", { name: "Save" }));
  expect(calls.find((c) => c.route === "POST /api/recurring")?.body).toMatchObject({
    label: "NETFLIX",
    amount: "-15.99",
    frequency: "monthly",
    day: 4,
    start_on: "2025-12-04",
  });

  await user.click(within(suggestions).getByRole("button", { name: "Dismiss NETFLIX" }));
  expect(calls.find((c) => c.route === "POST /api/recurring/suggestions/dismiss")?.body).toEqual({
    account_id: "a1",
    label: "NETFLIX",
  });
});

test("an item can be paused", async () => {
  const calls = api({
    "PATCH /api/recurring/r1": (body) => Response.json({ ...rent, ...(body as object) }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Pause LOYER" }));
  expect(calls.find((c) => c.route === "PATCH /api/recurring/r1")?.body).toEqual({ paused: true });
});

const joint = { ...checking, id: "a2", name: "Compte commun", visibility: "joint" };
const share = {
  ...rent,
  id: "r3",
  destination_account_id: "a2",
  destination_account_name: "Compte commun",
  category_id: null,
  category_name: null,
  label: "",
  amount: "-500.00",
  day: 5,
  next: { ...occurrence("2026-04-05", "upcoming"), item_id: "r3", expected: "-500.00" },
  recent: [{ ...occurrence("2026-03-05", "late"), item_id: "r3", expected: "-500.00" }],
};

test("a recurring transfer is saved between two accounts, without a category", async () => {
  const calls = api({
    "GET /api/accounts": () => Response.json([checking, joint]),
    "GET /api/recurring": () => Response.json([]),
    "POST /api/recurring": (body) =>
      Response.json({ ...share, ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a recurring item" }));
  const form = screen.getByRole("form", { name: "New recurring item" });
  await user.click(within(form).getByRole("radio", { name: "Transfer" }));
  expect(within(form).queryByLabelText("Category")).not.toBeInTheDocument();
  await user.selectOptions(within(form).getByLabelText("To account"), "a2");
  await user.type(within(form).getByLabelText("Amount (€)"), "500");
  await user.clear(within(form).getByLabelText("Day of the month"));
  await user.type(within(form).getByLabelText("Day of the month"), "5");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/recurring")?.body).toMatchObject({
    account_id: "a1",
    destination_account_id: "a2",
    category_id: null,
    label: "",
    amount: "-500.00",
    day: 5,
  });
});

test("enter it on a recurring transfer opens the transfer entry", async () => {
  const calls = api({
    "GET /api/accounts": () => Response.json([checking, joint]),
    "GET /api/recurring": () => Response.json([share]),
    "POST /api/transfers/entries": () =>
      Response.json({ group_id: "g1", outflow: {}, inflow: {} }, { status: 201 }),
  });
  render(<TestApp path="/recurring" />);

  const table = await screen.findByRole("table", { name: "Recurring" });
  expect(table).toHaveTextContent("Transfer to Compte commun");
  expect(table).toHaveTextContent("Compte courant → Compte commun");
  const user = userEvent.setup();
  await user.click(
    within(table).getByRole("button", { name: "Enter Transfer to Compte commun of 5 Mar 2026" }),
  );
  const form = screen.getByRole("form", { name: "New transaction" });
  expect(within(form).getByRole("radio", { name: "Transfer" })).toBeChecked();
  expect(within(form).getByLabelText("To account")).toHaveValue("a2");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/transfers/entries")?.body).toEqual({
    source_account_id: "a1",
    destination_account_id: "a2",
    booked_on: "2026-03-05",
    amount: "500.00",
    outflow_label: "Transfer to Compte commun",
    inflow_label: "Transfer from Compte courant",
  });
});

test("a recurring transfer needs two different accounts", async () => {
  const calls = api({
    "GET /api/accounts": () => Response.json([checking, joint]),
    "GET /api/recurring": () => Response.json([]),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a recurring item" }));
  const form = screen.getByRole("form", { name: "New recurring item" });
  await user.click(within(form).getByRole("radio", { name: "Transfer" }));
  await user.selectOptions(within(form).getByLabelText("To account"), "a1");
  await user.type(within(form).getByLabelText("Amount (€)"), "500");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(within(form).getByRole("alert")).toHaveTextContent(/two different accounts/);
  expect(calls.some((c) => c.route === "POST /api/recurring")).toBe(false);
});

test("enter it on a transfer to a closed account falls back to an open one", async () => {
  const savings = { ...checking, id: "a3", name: "Livret A", type: "savings" };
  api({
    "GET /api/accounts": () => Response.json([checking, savings]),
    "GET /api/recurring": () =>
      Response.json([{ ...share, destination_account_id: "a9", destination_account_name: "Old" }]),
  });
  render(<TestApp path="/recurring" />);

  const user = userEvent.setup();
  await user.click(
    await screen.findByRole("button", { name: "Enter Transfer to Old of 5 Mar 2026" }),
  );
  const form = screen.getByRole("form", { name: "New transaction" });
  expect(within(form).getByLabelText("To account")).toHaveValue("a3");
});
