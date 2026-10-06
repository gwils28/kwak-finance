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
  opening_balance: "100.00",
  opening_date: "2026-03-01",
  closed_on: null,
  balance: "1234.56",
};
const savings = { ...checking, id: "a2", name: "Livret A", type: "savings" };
const imported = {
  id: "t1",
  account_id: "a1",
  account_name: "Compte courant",
  booked_on: "2026-03-14",
  amount: "-4.20",
  label: "CARTE X0000 13/03 BOULANGERIE DU PARC",
  source: "import",
};
const manual = {
  ...imported,
  id: "t2",
  booked_on: "2026-03-12",
  amount: "2480.15",
  label: "Salary",
  source: "manual",
};

type Handler = (body: unknown) => Response;

function api(extra: Record<string, Handler> = {}, page = { items: [imported, manual], total: 2 }) {
  return fakeApi({
    "GET /api/auth/me": () => Response.json(owner),
    "GET /api/accounts": () => Response.json([checking, savings]),
    "GET /api/transactions": () => Response.json(page),
    ...extra,
  });
}

/** Query strings of every GET /api/transactions, from the fetch spy. */
function listQueries(): URLSearchParams[] {
  const fetchSpy = vi.mocked(fetch);
  return fetchSpy.mock.calls
    .map(([request]) => new URL((request as Request).url))
    .filter((url) => url.pathname === "/api/transactions")
    .map((url) => url.searchParams);
}

test("transactions are listed with their account and amount", async () => {
  api();
  render(<TestApp path="/transactions" />);

  const table = await screen.findByRole("table", { name: "Transactions" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("14 Mar 2026");
  expect(rows[0]).toHaveTextContent("BOULANGERIE DU PARC");
  expect(rows[0]).toHaveTextContent("Compte courant");
  expect(rows[0]).toHaveTextContent("-4,20 €");
  expect(rows[0]).toHaveTextContent("Imported");
  expect(within(rows[0] as HTMLElement).queryByRole("button", { name: /Edit/ })).toBeNull();
  expect(rows[1]).toHaveTextContent("2 480,15 €");
  expect(screen.getByText("2 transactions")).toBeInTheDocument();
});

test("an empty list says so", async () => {
  api({}, { items: [], total: 0 });
  render(<TestApp path="/transactions" />);
  expect(await screen.findByText(/No transactions match/)).toBeInTheDocument();
});

test("filters are sent to the API and kept in the address", async () => {
  api();
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await screen.findByRole("option", { name: "Livret A (Société Générale)" });
  await user.selectOptions(screen.getByLabelText("Account"), "a2");
  await user.type(screen.getByLabelText("From"), "2026-03-01");
  await user.type(screen.getByLabelText("Search"), "boulangerie{Enter}");

  await vi.waitFor(() => expect(listQueries().at(-1)?.get("q")).toBe("boulangerie"));
  const last = listQueries().at(-1);
  expect(last?.get("account_id")).toBe("a2");
  expect(last?.get("date_from")).toBe("2026-03-01");
});

test("emptying the search field drops the text filter", async () => {
  api();
  render(<TestApp path="/transactions?q=boulangerie" />);

  const user = userEvent.setup();
  await user.clear(await screen.findByLabelText("Search"));

  await vi.waitFor(() => expect(listQueries().at(-1)?.has("q")).toBe(false));
});

test("the accounts page links to an account's transactions", async () => {
  api();
  render(<TestApp path="/accounts" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Compte courant" }));

  expect(await screen.findByLabelText("Account")).toHaveValue("a1");
  expect(listQueries().at(-1)?.get("account_id")).toBe("a1");
});

test("pages move by 50", async () => {
  api({}, { items: [imported], total: 120 });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  expect(await screen.findByText("1–50 of 120")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Next" }));

  expect(await screen.findByText("51–100 of 120")).toBeInTheDocument();
  expect(listQueries().at(-1)?.get("offset")).toBe("50");
});

test("an expense is entered as a positive amount and stored negative", async () => {
  const calls = api({
    "POST /api/transactions": (body) =>
      Response.json({ ...manual, ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a transaction" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  await user.selectOptions(within(form).getByLabelText("Account"), "a1");
  await user.clear(within(form).getByLabelText("Date"));
  await user.type(within(form).getByLabelText("Date"), "2026-03-20");
  await user.type(within(form).getByLabelText("Amount (€)"), "12,5");
  await user.type(within(form).getByLabelText("Label"), "Market");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "POST /api/transactions")?.body).toEqual({
    account_id: "a1",
    booked_on: "2026-03-20",
    amount: "-12.50",
    label: "Market",
  });
});

test("income keeps a positive amount", async () => {
  const calls = api({
    "POST /api/transactions": (body) =>
      Response.json({ ...manual, ...(body as object) }, { status: 201 }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a transaction" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  await user.click(within(form).getByLabelText("Income"));
  await user.type(within(form).getByLabelText("Amount (€)"), "100");
  await user.type(within(form).getByLabelText("Label"), "Gift");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  const body = calls.find((c) => c.route === "POST /api/transactions")?.body as { amount: string };
  expect(body.amount).toBe("100.00");
});

test("a bad amount is refused before sending", async () => {
  const calls = api();
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Add a transaction" }));
  const form = screen.getByRole("form", { name: "New transaction" });
  await user.type(within(form).getByLabelText("Amount (€)"), "-3");
  await user.type(within(form).getByLabelText("Label"), "Oops");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(await within(form).findByRole("alert")).toHaveTextContent("Enter a positive amount");
  expect(calls.some((c) => c.route === "POST /api/transactions")).toBe(false);
});

test("a manual transaction can be edited", async () => {
  const calls = api({
    "PATCH /api/transactions/t2": (body) => Response.json({ ...manual, ...(body as object) }),
  });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Edit Salary" }));
  const form = screen.getByRole("form", { name: "Edit transaction" });
  expect(within(form).getByLabelText("Income")).toBeChecked();
  expect(within(form).getByLabelText("Amount (€)")).toHaveValue("2480,15");
  const label = within(form).getByLabelText("Label");
  await user.clear(label);
  await user.type(label, "Salary March");
  await user.click(within(form).getByRole("button", { name: "Save" }));

  expect(calls.find((c) => c.route === "PATCH /api/transactions/t2")?.body).toEqual({
    booked_on: "2026-03-12",
    amount: "2480.15",
    label: "Salary March",
  });
});

test("deleting a manual transaction asks for confirmation", async () => {
  const calls = api({ "DELETE /api/transactions/t2": () => new Response(null, { status: 204 }) });
  render(<TestApp path="/transactions" />);

  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Delete Salary" }));
  expect(calls.some((c) => c.route === "DELETE /api/transactions/t2")).toBe(false);
  await user.click(screen.getByRole("button", { name: "Confirm delete" }));

  expect(calls.some((c) => c.route === "DELETE /api/transactions/t2")).toBe(true);
});

test("the header links to the transactions page", async () => {
  api();
  render(<TestApp path="/" />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Transactions" }));
  expect(await screen.findByRole("heading", { name: "Transactions" })).toBeInTheDocument();
});
